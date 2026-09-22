#!/bin/sh
# Run x.com with extra V8/Chromium flags and say whether it crashed.
#
# usage: xtry.sh "<extra flags>" <seconds> <MMDDhhmmYYYY>
#
# The guest has no grep, sed, awk or pkill, and no persistent clock -- a wrong
# date fails TLS with ERR_CERT_DATE_INVALID before any of this means anything.
FLAGS="$1"
LIMIT=${2:-240}
[ -n "$3" ] && date "$3" > /dev/null

# Kill whatever the last run left behind.
if [ -f /boot/home/last.pid ]; then
    kill -9 "$(cat /boot/home/last.pid)" 2>/dev/null
    sleep 3
fi

cd /xfer2 || exit 1
export LIBRARY_PATH=/boot/home/cs/lib:/boot/system/lib
: > /boot/home/t.log
./content_shell --ozone-platform=haiku --no-sandbox --single-process \
    --disable-gpu --in-process-gpu --disable-gpu-compositing \
    --content-shell-host-window-size=1000x700 $FLAGS \
    https://x.com/i/flow/login > /boot/home/t.log 2>&1 &
pid=$!
echo "$pid" > /boot/home/last.pid

verdict="SURVIVED ${LIMIT}s"
i=0
while [ "$i" -lt "$LIMIT" ]; do
    sleep 5
    i=$((i + 5))
    dead=0
    while read -r l; do
        case "$l" in
            *"Check failed"*|*"Fatal error"*|*FATAL*) dead=1;;
        esac
    done < /boot/home/t.log
    if [ "$dead" = 1 ]; then
        verdict="CRASHED at ${i}s"
        break
    fi
done

echo "=============================="
echo "flags: ${FLAGS:-<none>}"
echo "RESULT: $verdict"
while read -r l; do
    case "$l" in
        *"Check failed"*|*"Fatal error"*) echo "  $l";;
    esac
done < /boot/home/t.log
echo "=============================="
kill -9 "$pid" 2>/dev/null
