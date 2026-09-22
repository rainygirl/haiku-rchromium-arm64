#!/bin/sh
# Does a page served from this machine crash the renderer the way x.com does?
#
# Every measurement of the AstValueFactory crash so far has been taken on
# x.com, and the baseline rate moved from 10/10 on 2026-09-21 to 3/6 on
# 2026-09-22 -- the site does not serve the same bundles twice, so there is no
# control to bisect a flag against. repro.html is generated from a fixed seed
# and served from the host over QEMU's user network: same bytes, same order,
# every run.
#
# The two arms are interleaved rather than run one after the other, so that a
# drift in the machine's own state (cache, free pages, uptime) lands on both
# instead of on whichever went second.
LIMIT=${1:-60}
[ -n "$2" ] && date "$2" > /dev/null
LOCAL="http://10.0.2.2:8000/repro.html"
REMOTE="https://x.com/i/flow/login"
OUT=/boot/home/rep.txt
: > "$OUT"
LR=""
RR=""
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
    log=/boot/home/rp$N.log
    killcs
    cd /xfer2 || exit 1
    export LIBRARY_PATH=/boot/home/cs/lib:/boot/system/lib
    ./content_shell --ozone-platform=haiku --no-sandbox --single-process \
        --disable-gpu --in-process-gpu --disable-gpu-compositing \
        --content-shell-host-window-size=1000x700 "$1" > "$log" 2>&1 &
    V="."
    i=0
    while [ "$i" -lt "$LIMIT" ]; do
        sleep 5
        i=$((i + 5))
        d=0
        while read -r l; do
            case "$l" in *"Check failed"*|*"Fatal error"*) d=1 ;; esac
        done < "$log"
        [ "$d" = 1 ] && { V="X"; break; }
    done
    killcs
}

k=0
while [ "$k" -lt 10 ]; do
    one "$LOCAL";  LR="$LR$V"
    one "$REMOTE"; RR="$RR$V"
    k=$((k + 1))
    printf 'local  %s\nx.com  %s\n' "$LR" "$RR" > "$OUT"
done
printf 'local  %s\nx.com  %s\nX = crashed, . = survived\n---- done ----\n' \
    "$LR" "$RR" > "$OUT"
