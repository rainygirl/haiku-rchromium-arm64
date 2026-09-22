#!/bin/sh
# PartitionAlloc against Haiku's own allocator, same boot, interleaved.
#
# BackupRefPtr came out 4 of 10 either way, which clears the pointer layer but
# not the allocator underneath it: the thread cache, the slot spans and the
# freelist encoding are untouched by that flag. This build has
# use_partition_alloc_as_malloc = false, so malloc in /xfer2/nopa/content_shell
# is libroot's.
#
# It matters for this crash because V8's AstRawStringMap -- the table whose
# keys stop pointing at live AstRawStrings -- is base::DefaultAllocationPolicy,
# which is plain malloc, while the strings themselves are in a Zone. And every
# native test ever written against this crash was built with the plain Haiku
# toolchain, so all of them measured libroot and none of them measured the
# allocator the browser actually runs on.
#
# Interleaved because the rate moves: x.com went 10/10, 3/6, 7/10 on three
# consecutive days, and the local page sits at 3 or 4 in ten.
LIMIT=${1:-60}
[ -n "$2" ] && date "$2" > /dev/null
URL=${3:-http://10.0.2.2:8000/repro2.html}
OUT=/boot/home/pa.txt
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
    log=/boot/home/pa$N.log
    killcs
    cd "$1" || exit 1
    export LIBRARY_PATH=/boot/home/cs/lib:/boot/system/lib
    ./content_shell --ozone-platform=haiku --no-sandbox --single-process \
        --disable-gpu --in-process-gpu --disable-gpu-compositing \
        --content-shell-host-window-size=1000x700 "$URL" > "$log" 2>&1 &
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

PA=""
NOPA=""
k=0
while [ "$k" -lt 10 ]; do
    one /xfer2;      PA="$PA$V"
    one /xfer2/nopa; NOPA="$NOPA$V"
    k=$((k + 1))
    printf 'partitionalloc %s\nlibroot        %s\n' "$PA" "$NOPA" > "$OUT"
done
printf 'partitionalloc %s\nlibroot        %s\nX = crashed, . = survived\n---- done ----\n' \
    "$PA" "$NOPA" > "$OUT"
