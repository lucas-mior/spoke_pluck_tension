#!/bin/sh

# shellcheck disable=SC2086

set -e

CC="${CC:-cc}"

CFLAGS="-g -O3 -march=native -fPIC -flto -D_DEFAULT_SOURCE -I cbase"
CFLAGS="$CFLAGS -Wall -Wextra"
CFLAGS="$CFLAGS -Werror"
CFLAGS="$CFLAGS -Wno-unused-macros"
CFLAGS="$CFLAGS -Wno-unused-function"
CFLAGS="$CFLAGS -Wno-discarded-qualifiers"

if [ "$CC" = "clang" ]; then
    CFLAGS="$CFLAGS -Weverything -Wno-format-nonliteral"
    CFLAGS="$CFLAGS -Wno-constant-logical-operand"
    CFLAGS="$CFLAGS -Wno-implicit-void-ptr-cast"
    CFLAGS="$CFLAGS -Wno-unsafe-buffer-usage"
fi

LDFLAGS="-lm -lrtaudio"

clean() {
    rm -f audio_to_fifo
}

build() {
    ctags --kinds-C=+l ./**/*.h ./**/*.c || true
    vtags.sed tags > .tags.vim || true
    
    $CC $CFLAGS -o audio_to_fifo audio_to_fifo.c $LDFLAGS
}

if [ "$1" = "clean" ]; then
    clean
else
    build
fi

