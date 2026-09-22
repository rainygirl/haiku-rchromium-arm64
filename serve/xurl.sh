#!/bin/sh
# Which pages crash? x.com is a slow, heavy reproducer; anything smaller that
# still crashes would make every later iteration cheaper, and a page that does
# not crash bounds what the trigger needs.
LIMIT=${1:-70}
[ -n "$2" ] && date "$2" > /dev/null
OUT=/boot/home/urls.txt
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
    N=$((N + 1))
    log=/boot/home/url$N.log
    killcs
    cd /xfer2 || exit 1
    export LIBRARY_PATH=/boot/home/cs/lib:/boot/system/lib
    ./content_shell --ozone-platform=haiku --no-sandbox --single-process \
        --disable-gpu --in-process-gpu --disable-gpu-compositing \
        --content-shell-host-window-size=1000x700 "$1" > "$log" 2>&1 &
    v="."
    i=0
    while [ "$i" -lt "$LIMIT" ]; do
        sleep 5
        i=$((i + 5))
        d=0
        while read -r l; do
            case "$l" in *"Check failed"*|*"Fatal error"*) d=1 ;; esac
        done < "$log"
        [ "$d" = 1 ] && { v="X"; break; }
    done
    printf '%s' "$v" >> "$OUT"
    killcs
}

site() {
    printf '%-40s ' "$1" >> "$OUT"
    one "$1"; one "$1"; one "$1"
    printf '\n' >> "$OUT"
}

site "https://x.com/i/flow/login"
site "https://x.com/"
site "https://ko.wikipedia.org/"
site "https://news.naver.com/"
site "https://www.google.com/"
echo "X = crashed, . = survived" >> "$OUT"
echo "---- done ----" >> "$OUT"
