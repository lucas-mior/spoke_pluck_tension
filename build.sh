#!/bin/sh

# Exit immediately if a command exits with a non-zero status
set -e

CC="clang"

CFLAGS="-g -O3 -march=native -fPIC -flto -D_DEFAULT_SOURCE -I cbase"
CFLAGS="$CFLAGS -Wall -Wextra"
CFLAGS="$CFLAGS -Wno-unsafe-buffer-usage -Wno-unused-macros -Wno-unused-function"
CFLAGS="$CFLAGS -Weverything -Wno-format-nonliteral"
CFLAGS="$CFLAGS -Wno-constant-logical-operand"
CFLAGS="$CFLAGS -Wno-implicit-void-ptr-cast"

LDFLAGS="-lm -lrtaudio"

clean() {
    rm -f audio_to_fifo
}

build() {
    # The '-' prefix in the Makefile ignores errors; '|| true' replicates this behavior
    ctags --kinds-C=+l ./**/*.h ./**/*.c || true
    vtags.sed tags > .tags.vim || true
    
    $CC $CFLAGS -o audio_to_fifo audio_to_fifo.c $LDFLAGS
}

if [ "$1" = "clean" ]; then
    clean
else
    build
fi

