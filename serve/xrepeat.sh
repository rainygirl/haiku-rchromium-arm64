#!/bin/sh
# Repeat the interesting flag sets three times each. One run proves nothing
# when the crash is a race: the first clean matrix had --single-threaded-gc
# crashing and --no-concurrent-sweeping surviving, which cannot both be true
# of the same mechanism.
LIMIT=${1:-70}
[ -n "$2" ] && date "$2" > /dev/null
OUT=/boot/home/repeat.txt
: > "$OUT"
N=0

killcs() {
    ps | while read -r line; do
        case "$line" in *content_shell*) ;; *) continue ;; esac
        # shellcheck disable=SC2086
        set -- $line
        n=$#
        [ "$n" -lt 4 ] && continue
        i=$((n - 3))
        eval "id=\${$i}"
        case "$id" in ''|*[!0-9]*) continue ;; esac
        kill -9 "$id" 2>/dev/null
    done
    sleep 4
}

one() {
    flags="$1"
    N=$((N + 1))
    log=/boot/home/rep$N.log
    killcs
    cd /xfer2 || exit 1
    export LIBRARY_PATH=/boot/home/cs/lib:/boot/system/lib
    ./content_shell --ozone-platform=haiku --no-sandbox --single-process \
        --disable-gpu --in-process-gpu --disable-gpu-compositing \
        --content-shell-host-window-size=1000x700 $flags \
        https://x.com/i/flow/login > "$log" 2>&1 &
    v="ok"
    i=0
    while [ "$i" -lt "$LIMIT" ]; do
        sleep 5
        i=$((i + 5))
        d=0
        while read -r l; do
            case "$l" in *"Check failed"*|*"Fatal error"*) d=1 ;; esac
        done < "$log"
        [ "$d" = 1 ] && { v="CRASH"; break; }
    done
    printf '%s' "$v " >> "$OUT"
    killcs
}

trial() {
    printf '%-24s ' "$1" >> "$OUT"
    one "$2"; one "$2"; one "$2"
    printf '\n' >> "$OUT"
}

trial "baseline"              ""
trial "single-threaded"       "--js-flags=--single-threaded"
trial "single-threaded-gc"    "--js-flags=--single-threaded-gc"
trial "no-concurrent-sweep"   "--js-flags=--no-concurrent-sweeping"
echo "---- done ----" >> "$OUT"
