#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <portaudio.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>

typedef int16_t int16;

#define SAMPLE_RATE 44100
#define FRAMES_PER_BUFFER 4096
#define FIFO_PATH "/tmp/audio_fifo"

static int
audio_callback(const void *inputBuffer,
               void *outputBuffer,
               unsigned long framesPerBuffer,
               const PaStreamCallbackTimeInfo *timeInfo,
               PaStreamCallbackFlags statusFlags,
               void *userData) {
    int *fifo = userData;
    int16 *in = inputBuffer;

    if (inputBuffer == NULL) {
        for (unsigned long i = 0; i < framesPerBuffer; i++) {
            int16 zero = 0;
            write(*fifo, &zero, 1);
        }
    } else {
        write(*fifo, in, framesPerBuffer*sizeof(int16));
    }

    return paContinue;
}

int main(void) {
    PaStream *stream;
    PaError pa_error;

    int fifo = open(FIFO_PATH, O_WRONLY);
    if (fifo < 0) {
        fprintf(stderr, "Error opening %s: %s.\n", FIFO_PATH, strerror(errno));
        return 1;
    }

    pa_error = Pa_Initialize();
    if (pa_error != paNoError)
        goto error;

    pa_error = Pa_OpenDefaultStream(&stream,
                               1,
                               0,
                               paInt16,
                               SAMPLE_RATE,
                               FRAMES_PER_BUFFER,
                               audio_callback,
                               &fifo);
    if (pa_error != paNoError)
        goto error;

    pa_error = Pa_StartStream(stream);
    if (pa_error != paNoError)
        goto error;

    printf("Streaming audio to FIFO... Press Ctrl+C to stop.\n");
    while (1) {
        sleep(1);  // Keep running
    }

    Pa_StopStream(stream);
    Pa_CloseStream(stream);
    Pa_Terminate();
    close(fifo);

    return 0;

error:
    fprintf(stderr, "PortAudio error: %s\n", Pa_GetErrorText(pa_error));
    return 1;
}
