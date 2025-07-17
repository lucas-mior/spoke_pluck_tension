#include <stdio.h>
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

atomic_int overflow_count = 0;
volatile sig_atomic_t running = 1;

int16 buffer[FRAMES_PER_BUFFER] = {0};

int
record_callback(void *outputBuffer, void *inputBuffer,
                unsigned int nFrames, double streamTime,
                unsigned int status, void *userData) {
    int *fifo = userData;
    const int16 *in = inputBuffer;

    if (status & RTAUDIO_STATUS_INPUT_OVERFLOW) {
        printf("INPUT_OVERFLOW\n");
        atomic_fetch_add(&overflow_count, 1);
    }
    if (status & RTAUDIO_STATUS_OUTPUT_UNDERFLOW) {
        printf("OUTPUT_UNDERFLOW\n");
        atomic_fetch_add(&overflow_count, 1);
    }

    if (!in) {
        int16 zero = 0;
        write(*fifo, &buffer, sizeof(buffer));
    } else {
        write(*fifo, in, nFrames*sizeof(*in));
    }

    return 0;
}

void sigint_handler(int signum) {
    running = 0;
}

int main(void) {
    rtaudio_stream_parameters_t rt_stream_params;
    rtaudio_stream_options_t rt_stream_options;
    rtaudio_t io = NULL;
    int fifo;
    int total = 0;
    int seconds = 0;

    /* signal(SIGINT, sigint_handler); */

    if ((fifo = open(FIFO_PATH, O_WRONLY)) < 0) {
        fprintf(stderr, "Error opening %s: %s.\n", FIFO_PATH, strerror(errno));
        exit(EXIT_FAILURE);
    }

    if ((io = rtaudio_create(RTAUDIO_API_UNSPECIFIED)) == NULL) {
        fprintf(stderr, "Error initializing RtAudio.\n");
        exit(EXIT_FAILURE);
    }

    rt_stream_params.device_id    = rtaudio_get_default_input_device(io);
    rt_stream_params.num_channels = 1;
    rt_stream_params.first_channel = 0;

    rt_stream_options.flags = 0;
    rt_stream_options.num_buffers = 0;
    rt_stream_options.priority = 0;
    rt_stream_options.name[0] = '\0';

    unsigned int buffer_frames = FRAMES_PER_BUFFER;
    if (rtaudio_open_stream(io, NULL, &rt_stream_params,
                            RTAUDIO_FORMAT_SINT16,
                            SAMPLE_RATE, &buffer_frames,
                            record_callback, &fifo,
                            &rt_stream_options, NULL) != RTAUDIO_ERROR_NONE) {
        fprintf(stderr, "Error opening RtAudio stream: %s\n", rtaudio_error(io));
        exit(EXIT_FAILURE);
    }

    if (rtaudio_start_stream(io) != RTAUDIO_ERROR_NONE) {
        fprintf(stderr, "Error starting RtAudio stream: %s\n", rtaudio_error(io));
        exit(EXIT_FAILURE);
    }

    printf("Streaming audio to FIFO... Press Ctrl+C to stop.\n");

#define SLEEP 2
    while (running) {
        sleep(SLEEP);
        int count = atomic_exchange(&overflow_count, 0);
        total += count;
        seconds += SLEEP;
        double average = (double)total / seconds;
        printf("Input overflows in last %d seconds: %d | average: %.2f/s\n",
               SLEEP, count, average);
    }

    rtaudio_stop_stream(io);
    rtaudio_close_stream(io);
    rtaudio_destroy(io);
    close(fifo);

    return 0;
}
