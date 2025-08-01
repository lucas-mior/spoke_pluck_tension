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

static atomic_int had_overflow = 0;
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
record_callback(void *output_buffer, void *input_buffer,
                unsigned int number_frames, double stream_time,
                unsigned int status, void *user_data) {
    static int16 dummy_buffer[FRAMES_PER_BUFFER] = {0};
    int *fifo = user_data;
    const int16 *in = input_buffer;
    (void) output_buffer;
    (void) stream_time;

    if (status & RTAUDIO_STATUS_INPUT_OVERFLOW) {
        error("rtaudio: input overflow.\n");
        atomic_fetch_add(&had_overflow, 1);
    }
    if (status & RTAUDIO_STATUS_OUTPUT_UNDERFLOW) {
        error("rtaudio: output underflow.\n");
        atomic_fetch_add(&had_overflow, 1);
    }

    if (!in)
        write(*fifo, &dummy_buffer, sizeof(dummy_buffer));
    else
        write(*fifo, in, number_frames*sizeof(*in));

    return 0;
}

static void
sigint_handler(int signum) {
    (void) signum;
    running = 0;
}

int
main(void) {
    int fifo;
    int total = 0;
    uint32 buffer_frames;

    rtaudio_stream_parameters_t rt_stream_params;
    rtaudio_stream_options_t rt_stream_options;
    rtaudio_t rt_handle = NULL;

    signal(SIGINT, sigint_handler);

    if ((fifo = open(FIFO_PATH, O_WRONLY)) < 0) {
        error("Error opening %s: %s.\n", FIFO_PATH, strerror(errno));
        exit(EXIT_FAILURE);
    }
    if ((rt_handle = rtaudio_create(RTAUDIO_API_LINUX_PULSE)) == NULL) {
        error("Error initializing RtAudio.\n");
        exit(EXIT_FAILURE);
    }

    rt_stream_params.device_id = rtaudio_get_default_input_device(rt_handle);
    rt_stream_params.num_channels = 1;
    rt_stream_params.first_channel = 0;

    rt_stream_options.flags = 0;
    rt_stream_options.num_buffers = 0;
    rt_stream_options.priority = 0;
    rt_stream_options.name[0] = '\0';

    buffer_frames = FRAMES_PER_BUFFER;
    if (rtaudio_open_stream(rt_handle, NULL, &rt_stream_params,
                            RTAUDIO_FORMAT_SINT16,
                            SAMPLE_RATE, &buffer_frames,
                            record_callback, &fifo,
                            &rt_stream_options, NULL) != RTAUDIO_ERROR_NONE) {
        error("Error opening RtAudio stream: %s\n", rtaudio_error(rt_handle));
        exit(EXIT_FAILURE);
    }

    if (rtaudio_start_stream(rt_handle) != RTAUDIO_ERROR_NONE) {
        error("Error starting RtAudio stream: %s\n", rtaudio_error(rt_handle));
        exit(EXIT_FAILURE);
    }

    printf("Streaming audio to FIFO... Press Ctrl+C to stop.\n");

    while (running) {
        static int seconds = 0;
        int overflow_count;
        double average;
        sleep(OVERFLOW_CHECK_INTERVAL);

        overflow_count = atomic_exchange(&had_overflow, 0);
        total += overflow_count;
        seconds += OVERFLOW_CHECK_INTERVAL;

        average = (double)total / seconds;
        if ((average > 0.1) || (overflow_count > 0)) {
            error("Input overflows in last %d seconds: %d | average: %.2f/s\n",
                  OVERFLOW_CHECK_INTERVAL, overflow_count, average);
        }
    }

    rtaudio_stop_stream(rt_handle);
    rtaudio_close_stream(rt_handle);
    rtaudio_destroy(rt_handle);
    close(fifo);

    return 0;
}
