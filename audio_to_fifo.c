#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <portaudio.h>
#include <stdint.h>

typedef int16_t int16;

#define SAMPLE_RATE 44100
#define FRAMES_PER_BUFFER 4096
#define FIFO_PATH "/tmp/audio_fifo"

static int audio_callback(const void *inputBuffer, void *outputBuffer,
                          unsigned long framesPerBuffer,
                          const PaStreamCallbackTimeInfo* timeInfo,
                          PaStreamCallbackFlags statusFlags,
                          void *userData) {
    FILE *fifo = (FILE *)userData;
    const int16 *in = (const int16 *)inputBuffer;

    if (inputBuffer == NULL) {
        for (unsigned long i = 0; i < framesPerBuffer; i++) {
            int16 zero = 0;
            fwrite(&zero, sizeof(int16), 1, fifo);
        }
    } else {
        fwrite(in, sizeof(int16), framesPerBuffer, fifo);
    }

    fflush(fifo);
    return paContinue;
}

int main(void) {
    PaStream *stream;
    PaError err;

    FILE *fifo = fopen(FIFO_PATH, "wb");
    if (!fifo) {
        perror("fopen FIFO");
        return 1;
    }

    err = Pa_Initialize();
    if (err != paNoError)
        goto error;

    err = Pa_OpenDefaultStream(&stream,
                               1,
                               0,
                               paInt16,
                               SAMPLE_RATE,
                               FRAMES_PER_BUFFER,
                               audio_callback,
                               fifo);
    if (err != paNoError)
        goto error;

    err = Pa_StartStream(stream);
    if (err != paNoError)
        goto error;

    printf("Streaming audio to FIFO... Press Ctrl+C to stop.\n");
    while (1) {
        sleep(1);  // Keep running
    }

    Pa_StopStream(stream);
    Pa_CloseStream(stream);
    Pa_Terminate();
    fclose(fifo);

    return 0;

error:
    fprintf(stderr, "PortAudio error: %s\n", Pa_GetErrorText(err));
    return 1;
}
