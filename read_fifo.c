#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>
#include <errno.h>
#include <signal.h>
#include <time.h>
#include <poll.h>

#define FIFO_PATH "/tmp/audio_fifo"
#define BUFFER_SIZE 4096

volatile sig_atomic_t running = 1;

void sigint_handler(int signum) {
    running = 0;
}

int main(void) {
    int fifo;
    char buffer[BUFFER_SIZE];
    ssize_t bytes_read;
    ssize_t total = 0;

    signal(SIGINT, sigint_handler);

    if ((fifo = open(FIFO_PATH, O_RDONLY | O_NONBLOCK)) < 0) {
        fprintf(stderr, "Error opening %s: %s\n", FIFO_PATH, strerror(errno));
        exit(EXIT_FAILURE);
    }

    struct pollfd pfd = {
        .fd = fifo,
        .events = POLLIN
    };

    printf("Reading from FIFO... Press Ctrl+C to stop.\n");

    while (running) {
        total = 0;
        time_t start = time(NULL);
        while (time(NULL) == start && running) {
            int ret = poll(&pfd, 1, 100); // 100 ms timeout
            if (ret > 0 && (pfd.revents & POLLIN)) {
                bytes_read = read(fifo, buffer, sizeof(buffer));
                if (bytes_read > 0) {
                    total += bytes_read;
                }
            }
        }
        printf("Bytes read in last second: %zd\n", total);
    }

    close(fifo);
    return 0;
}
