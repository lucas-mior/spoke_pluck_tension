#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <portaudio.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <signal.h>
#include <stdatomic.h>
#include <time.h>

typedef int16_t int16;

#define SAMPLE_RATE 44100
#define FRAMES_PER_BUFFER 4096
#define FIFO_PATH "/tmp/audio_fifo"

atomic_int overflow_count = 0;
volatile sig_atomic_t running = 1;

static int
audio_callback(const void *inputBuffer,
               void *outputBuffer,
               unsigned long framesPerBuffer,
               const PaStreamCallbackTimeInfo *timeInfo,
               PaStreamCallbackFlags statusFlags,
               void *userData) {
    int *fifo = userData;
    const int16 *in = inputBuffer;
    (void) outputBuffer;
    (void) timeInfo;

    if (statusFlags & paInputOverflow) {
        atomic_fetch_add(&overflow_count, 1);
    }

    if (inputBuffer == NULL) {
        int16 zero = 0;
        for (unsigned long i = 0; i < framesPerBuffer; i++) {
            write(*fifo, &zero, sizeof(zero));
        }
    } else {
        write(*fifo, in, framesPerBuffer * sizeof(*in));
    }

    return paContinue;
}

void sigint_handler(int signum) {
    running = 0;
}

int main(void) {
    PaStream *stream;
    PaError pa_error;
    int fifo;
    int total = 0;
    int seconds = 0;

    signal(SIGINT, sigint_handler);

    if ((fifo = open(FIFO_PATH, O_WRONLY)) < 0) {
        fprintf(stderr, "Error opening %s: %s.\n", FIFO_PATH, strerror(errno));
        exit(EXIT_FAILURE);
    }

    if ((pa_error = Pa_Initialize()) != paNoError) {
        fprintf(stderr, "Error initializing PortAudio: %s.\n", Pa_GetErrorText(pa_error));
        exit(EXIT_FAILURE);
    }

    pa_error = Pa_OpenDefaultStream(&stream,
                                    1, 0,
                                    paInt16,
                                    SAMPLE_RATE,
                                    FRAMES_PER_BUFFER,
                                    audio_callback,
                                    &fifo);
    if (pa_error != paNoError) {
        fprintf(stderr, "Error opening PortAudio stream: %s.\n", Pa_GetErrorText(pa_error));
        exit(EXIT_FAILURE);
    }

    if ((pa_error = Pa_StartStream(stream)) != paNoError) {
        fprintf(stderr, "Error starting PortAudio stream: %s.\n", Pa_GetErrorText(pa_error));
        exit(EXIT_FAILURE);
    }

    printf("Streaming audio to FIFO... Press Ctrl+C to stop.\n");

    while (running) {
        sleep(1);
        int count = atomic_exchange(&overflow_count, 0);
        total += count;
        seconds += 1;
        double average = (double) total / seconds;
        printf("Input overflow count in last second: %d | average: %.2f/s\n", count, average);
    }

    Pa_StopStream(stream);
    Pa_CloseStream(stream);
    Pa_Terminate();
    close(fifo);

    exit(EXIT_SUCCESS);
}
