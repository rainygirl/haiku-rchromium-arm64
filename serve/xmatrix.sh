#!/bin/sh
# Run x.com once per flag set and print a one-line verdict for each.
#
# usage: xmatrix.sh <seconds-per-run> <MMDDhhmmYYYY>
#
# The guest has no grep, sed, awk, pkill or killall, and no persistent clock.
# Each run gets its own log: sharing one file let an orphan from an earlier run
# write a fatal line into the next run's log, which reported "--single-threaded
# crashed" -- the one result this file says cannot happen.
LIMIT=${1:-70}
[ -n "$2" ] && date "$2" > /dev/null
OUT=/boot/home/matrix.txt
: > "$OUT"
N=0

# ps prints: <command...> <team> <threads> <gid> <uid>, so the team id is the
# fourth field from the end and the command may contain spaces.
killcs() {
    ps | while read -r line; do
        case "$line" in
            *content_shell*) ;;
            *) continue ;;
        esac
        # shellcheck disable=SC2086
        set -- $line
        n=$#
        [ "$n" -lt 4 ] && continue
        i=$((n - 3))
        eval "id=\${$i}"
        case "$id" in
            ''|*[!0-9]*) continue ;;
        esac
        kill -9 "$id" 2>/dev/null
    done
    sleep 4
}

try() {
    label="$1"
    flags="$2"
    N=$((N + 1))
    log=/boot/home/run$N.log
    killcs
    cd /xfer2 || exit 1
    export LIBRARY_PATH=/boot/home/cs/lib:/boot/system/lib
    ./content_shell --ozone-platform=haiku --no-sandbox --single-process \
        --disable-gpu --in-process-gpu --disable-gpu-compositing \
        --content-shell-host-window-size=1000x700 $flags \
        https://x.com/i/flow/login > "$log" 2>&1 &
    v="SURVIVED"
    i=0
    while [ "$i" -lt "$LIMIT" ]; do
        sleep 5
        i=$((i + 5))
        d=0
        while read -r l; do
            case "$l" in *"Check failed"*|*"Fatal error"*) d=1 ;; esac
        done < "$log"
        [ "$d" = 1 ] && { v="CRASHED@${i}s"; break; }
    done
    printf '%-26s %-12s %s\n' "$label" "$v" "run$N.log" >> "$OUT"
    killcs
}

try "baseline"              ""
try "single-threaded"       "--js-flags=--single-threaded"
try "single-threaded-gc"    "--js-flags=--single-threaded-gc"
try "no-concurrent-marking" "--js-flags=--no-concurrent-marking"
try "no-concurrent-sweeping" "--js-flags=--no-concurrent-sweeping"
try "no-concurrent-recomp"  "--js-flags=--no-concurrent-recompilation"

echo "---- done ----" >> "$OUT"
