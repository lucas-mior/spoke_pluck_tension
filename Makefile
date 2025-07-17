CC = clang

CFLAGS = -g -O3 -march=native -fPIC -flto -D_DEFAULT_SOURCE
CFLAGS += -Wall -Wextra -Wno-unsafe-buffer-usage -Wno-unused-macros -Wno-unused-function
CFLAGS += -Weverything -Wno-format-nonliteral
CFLAGS += -Wfatal-errors -Werror

LDFLAGS = -lm -lrtaudio

SRC = audio_to_fifo.c

all: audio_to_fifo

audio_to_fifo: $(SRC) Makefile
	-ctags --kinds-C=+l *.h *.c
	-vtags.sed tags > .tags.vim
	$(CC) $(CFLAGS) -o audio_to_fifo $(LDFLAGS) $(SRC)

clean:
	rm audio_to_fifo
