#!/bin/sh
# Ten runs of ko.wikipedia.org. It crashed once in three during the URL sweep,
# and if it reproduces at a usable rate it is a far cheaper reproducer than
# x.com: a fraction of the JS and it finishes loading on this VM.
LIMIT=${1:-70}
[ -n "$2" ] && date "$2" > /dev/null
OUT=/boot/home/wiki.txt
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
    N=$((N + 1)); log=/boot/home/wk$N.log
    killcs
    cd /xfer2 || exit 1
    export LIBRARY_PATH=/boot/home/cs/lib:/boot/system/lib
    ./content_shell --ozone-platform=haiku --no-sandbox --single-process \
        --disable-gpu --in-process-gpu --disable-gpu-compositing \
        --content-shell-host-window-size=1000x700 "$1" > "$log" 2>&1 &
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
printf '%-26s ' "ko.wikipedia.org" >> "$OUT"
k=0; while [ "$k" -lt 10 ]; do one "https://ko.wikipedia.org/"; k=$((k + 1)); done
printf '\n' >> "$OUT"
echo "X = crashed, . = survived" >> "$OUT"
echo "---- done ----" >> "$OUT"
