#!/bin/sh -e

# shellcheck disable=SC2086

dir=$(dirname "$(readlink -f "$0")")
cd "$dir" || exit

# shellcheck source=./cbase/common.sh
. "./cbase/common.sh"

script=$(basename "$0")
common_build_parse_args "$@"

case "$mode" in
build|check|clean|debug|debug-fast|fast_feedback|install|test|uninstall)
    ;;
*)
    common_build_unknown_mode
    ;;
esac

common_build_print_invocation "$script"

PREFIX="${PREFIX:-/usr/local}"
DESTDIR="${DESTDIR:-/}"

program="audio_to_fifo"
exe="bin/$program"
mkdir -p "$(dirname "$exe")"

CC=$(common_get_compiler "$mode")

CPPFLAGS="$CPPFLAGS -I$dir/cbase"

CFLAGS="$CFLAGS -std=c11"
CFLAGS="$CFLAGS -Wfatal-errors"
# CFLAGS="$CFLAGS -Werror"  # Only uncomment occasionally, keep this line

LDFLAGS="$LDFLAGS -lm -lrtaudio"

case "$mode" in
debug)
    CFLAGS="$CFLAGS -g3 -Og"
    CPPFLAGS="$CPPFLAGS -DDEBUGGING=1"
    exe="bin/$program"
    ;;
debug-fast)
    CFLAGS="$CFLAGS -g2 -O2 -flto -march=native -ftree-vectorize"
    CPPFLAGS="$CPPFLAGS -DDEBUGGING=1"
    ;;
build)
    CFLAGS="$CFLAGS -O2 -flto -march=native -ftree-vectorize"
    ;;
fast_feedback)
    ;;
test|install|uninstall|clean)
    ;;
build|check|clean|debug|debug-fast|fast_feedback|install|test|uninstall)
    ;;
*)
    common_build_unknown_mode
    ;;
esac

build_program () {
    common_build_tags
    trace_on
    $CC $CPPFLAGS $CFLAGS -o "$exe" audio_to_fifo.c $LDFLAGS
    trace_off
}

case "$mode" in
clean)
    trace_on
    rm -rf bin tags .tags.vim
    trace_off
    ;;
fast_feedback)
    build_program
    ;;
test)
    TEST_EXCLUDE_PATTERN='(^|/)cbase/' common_test "$target"
    exit
    ;;
check)
    common_build_run_analyzers build
    ;;
uninstall)
    trace_on
    rm -f "${DESTDIR}${PREFIX}/bin/${program}"
    trace_off
    ;;
install)
    if [ ! -f "$exe" ]; then
        "$0" build
    fi
    trace_on
    install -Dm755 "$exe" "${DESTDIR}${PREFIX}/bin/${program}"
    trace_off
    ;;
build|debug|debug-fast|fast_feedback)
    build_program
    ;;
esac
