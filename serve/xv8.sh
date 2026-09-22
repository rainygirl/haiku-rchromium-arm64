#!/bin/sh
# Six runs per arm across axes that change what V8 does rather than how many
# threads it uses. Baseline is 10/10, so an arm that comes out clean six times
# is a real signal; three runs proved nothing last time.
LIMIT=${1:-70}
[ -n "$2" ] && date "$2" > /dev/null
OUT=/boot/home/v8arms.txt
: > "$OUT"
N=0
killcs() {
    ps | while read -r line; do
        case "$line" in *content_shell*) ;; *) continue ;; esac
        # shellcheck disable=SC2086
        set -- $line
        n=$#; [ "$n" -lt 4 ] && continue
        i=$((n - 3)); eval "id=\${$i}"
        case "$id" in ''|*[!0-9]*) continue ;; esac
        kill -9 "$id" 2>/dev/null
    done
    sleep 4
}
one() {
    N=$((N + 1)); log=/boot/home/v8_$N.log
    killcs
    cd /xfer2 || exit 1
    export LIBRARY_PATH=/boot/home/cs/lib:/boot/system/lib
    ./content_shell --ozone-platform=haiku --no-sandbox --single-process \
        --disable-gpu --in-process-gpu --disable-gpu-compositing \
        --content-shell-host-window-size=1000x700 $1 \
        https://x.com/i/flow/login > "$log" 2>&1 &
    v="."; i=0
    while [ "$i" -lt "$LIMIT" ]; do
        sleep 5; i=$((i + 5)); d=0
        while read -r l; do
            case "$l" in *"Check failed"*|*"Fatal error"*) d=1 ;; esac
        done < "$log"
        [ "$d" = 1 ] && { v="X"; break; }
    done
    printf '%s' "$v" >> "$OUT"
    killcs
}
arm() {
    printf '%-22s ' "$1" >> "$OUT"
    k=0; while [ "$k" -lt 6 ]; do one "$2"; k=$((k + 1)); done
    printf '\n' >> "$OUT"
}
arm "baseline"    ""
arm "jitless"     "--js-flags=--jitless"
arm "predictable" "--js-flags=--predictable"
arm "no-lazy"     "--js-flags=--no-lazy"
echo "X = crashed, . = survived" >> "$OUT"
echo "---- done ----" >> "$OUT"
