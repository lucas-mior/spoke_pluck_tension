#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>
#include <stdatomic.h>
#include <time.h>
#include <rtaudio/rtaudio_c.h>

typedef int16_t int16;

#define SAMPLE_RATE 44100
#define FRAMES_PER_BUFFER 4096
#define FIFO_PATH "/tmp/audio_fifo"
#define OVERFLOW_CHECK_INTERVAL 2

static atomic_int overflow_count = 0;
static volatile sig_atomic_t running = 1;

#ifndef INTEGERS
#define INTEGERS
typedef unsigned char uchar;
typedef unsigned short ushort;
typedef unsigned int uint;
typedef unsigned long ulong;
typedef unsigned long long ulonglong;

typedef int8_t int8;
typedef int16_t int16;
typedef int32_t int32;
typedef int64_t int64;
typedef uint8_t uint8;
typedef uint16_t uint16;
typedef uint32_t uint32;
typedef uint64_t uint64;

typedef size_t usize;
typedef ssize_t isize;
#endif

static void
error(char *format, ...) {
    char buffer[BUFSIZ];
    va_list args;
    int32 n;

    va_start(args, format);
    n = vsnprintf(buffer, sizeof(buffer) - 1, format, args);
    va_end(args);

    if (n < 0 || n > (int32)sizeof(buffer)) {
        fprintf(stderr, "Error in vsnprintf()\n");
        exit(EXIT_FAILURE);
    }

    buffer[n] = '\0';
    write(STDERR_FILENO, buffer, (usize)n);
    return;
}

static int
record_callback(void *outputBuffer, void *inputBuffer,
                unsigned int nFrames, double streamTime,
                unsigned int status, void *userData) {
    static int16 dummy_buffer[FRAMES_PER_BUFFER] = {0};
    int *fifo = userData;
    const int16 *in = inputBuffer;
    (void) outputBuffer;
    (void) streamTime;

    if (status & RTAUDIO_STATUS_INPUT_OVERFLOW) {
        printf("INPUT_OVERFLOW\n");
        atomic_fetch_add(&overflow_count, 1);
    }
    if (status & RTAUDIO_STATUS_OUTPUT_UNDERFLOW) {
        printf("OUTPUT_UNDERFLOW\n");
        atomic_fetch_add(&overflow_count, 1);
    }

    if (!in)
        write(*fifo, &dummy_buffer, sizeof(dummy_buffer));
    else
        write(*fifo, in, nFrames*sizeof(*in));

    return 0;
}

static void
sigint_handler(int signum) {
    (void) signum;
    running = 0;
}

int main(void) {
    rtaudio_stream_parameters_t rt_stream_params;
    rtaudio_stream_options_t rt_stream_options;
    rtaudio_t io = NULL;
    int fifo;
    int total = 0;
    int seconds = 0;
    uint32 buffer_frames;

    signal(SIGINT, sigint_handler);

    if ((fifo = open(FIFO_PATH, O_WRONLY)) < 0) {
        error("Error opening %s: %s.\n", FIFO_PATH, strerror(errno));
        exit(EXIT_FAILURE);
    }

    if ((io = rtaudio_create(RTAUDIO_API_UNSPECIFIED)) == NULL) {
        error("Error initializing RtAudio.\n");
        exit(EXIT_FAILURE);
    }

    rt_stream_params.device_id    = rtaudio_get_default_input_device(io);
    rt_stream_params.num_channels = 1;
    rt_stream_params.first_channel = 0;

    rt_stream_options.flags = 0;
    rt_stream_options.num_buffers = 0;
    rt_stream_options.priority = 0;
    rt_stream_options.name[0] = '\0';

    buffer_frames = FRAMES_PER_BUFFER;
    if (rtaudio_open_stream(io, NULL, &rt_stream_params,
                            RTAUDIO_FORMAT_SINT16,
                            SAMPLE_RATE, &buffer_frames,
                            record_callback, &fifo,
                            &rt_stream_options, NULL) != RTAUDIO_ERROR_NONE) {
        error("Error opening RtAudio stream: %s\n", rtaudio_error(io));
        exit(EXIT_FAILURE);
    }

    if (rtaudio_start_stream(io) != RTAUDIO_ERROR_NONE) {
        error("Error starting RtAudio stream: %s\n", rtaudio_error(io));
        exit(EXIT_FAILURE);
    }

    printf("Streaming audio to FIFO... Press Ctrl+C to stop.\n");

    while (running) {
        int count;
        double average;
        sleep(OVERFLOW_CHECK_INTERVAL);

        count = atomic_exchange(&overflow_count, 0);
        total += count;
        seconds += OVERFLOW_CHECK_INTERVAL;

        average = (double)total / seconds;
        if ((average > 0.1) || (count > 0)) {
            printf("Input overflows in last %d seconds: %d | average: %.2f/s\n",
                   OVERFLOW_CHECK_INTERVAL, count, average);
        }
    }

    rtaudio_stop_stream(io);
    rtaudio_close_stream(io);
    rtaudio_destroy(io);
    close(fifo);

    return 0;
}
