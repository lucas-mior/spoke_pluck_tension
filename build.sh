#!/bin/sh

# shellcheck disable=SC2086

set -e

CC="${CC:-gcc}"

CPPFLAGS="$CPPFLAGS -D_DEFAULT_SOURCE -D_XOPEN_SOURCE=700"
CPPFLAGS="$CPPFLAGS -Icbase"

CFLAGS="$CFLAGS -std=c11"
CFLAGS="$CFLAGS -g -O3 -march=native -fPIC -flto"
CFLAGS="$CFLAGS -Wall -Wextra"
CFLAGS="$CFLAGS -Werror"
CFLAGS="$CFLAGS -Wno-unused-macros"
CFLAGS="$CFLAGS -Wno-unused-function"
CFLAGS="$CFLAGS -Wno-unknown-warning-option"

if [ "$CC" = gcc ]; then
    CFLAGS="$CFLAGS -Wno-discarded-qualifiers"
fi

if [ "$CC" = "clang" ]; then
    CFLAGS="$CFLAGS -Weverything"
    CFLAGS="$CFLAGS -Wno-format-nonliteral"
    CFLAGS="$CFLAGS -Wno-constant-logical-operand"
    CFLAGS="$CFLAGS -Wno-implicit-void-ptr-cast"
    CFLAGS="$CFLAGS -Wno-unsafe-buffer-usage"
    CFLAGS="$CFLAGS -Wno-pre-c11-compat"
    CFLAGS="$CFLAGS -Wno-c++-keyword"
    CFLAGS="$CFLAGS -Wno-cast-qual"
    CFLAGS="$CFLAGS -Wno-gnu-union-cast"
    CFLAGS="$CFLAGS -Wno-cast-function-type-strict"
    CFLAGS="$CFLAGS -Wno-padded"
    CFLAGS="$CFLAGS -Wno-covered-switch-default"
    CFLAGS="$CFLAGS -Wno-float-equal"
    CFLAGS="$CFLAGS -Wno-incompatible-pointer-types-discards-qualifiers"
    CFLAGS="$CFLAGS -Wno-assign-enum"
    CFLAGS="$CFLAGS -Wno-implicit-int-enum-cast"
fi

LDFLAGS="-lm -lrtaudio"

clean () {
    rm -f audio_to_fifo
}

build () {
    ctags --kinds-C=+l ./**/*.h ./**/*.c || true
    vtags.sed tags > .tags.vim || true
    
    $CC $CPPFLAGS $CFLAGS -o audio_to_fifo audio_to_fifo.c $LDFLAGS
}

case "${1:-build}" in
"clean")
    clean
    ;;
"check")
    CC=gcc CFLAGS="-fanalyzer -fdiagnostics-color=never" "$0" build
    CFLAGS="--analyze -Xanalyzer -analyzer-output=text"
    CFLAGS="$CFLAGS -Xanalyzer -analyzer-werror"
    CFLAGS="$CFLAGS -Xanalyzer -analyzer-opt-analyze-headers"
    CFLAGS="$CFLAGS -Wno-unused-command-line-argument"
    CFLAGS="$CFLAGS -fno-color-diagnostics"
    CC=clang CFLAGS="$CFLAGS" "$0" build
    ;;
"build"|*)
    build
    ;;
esac
