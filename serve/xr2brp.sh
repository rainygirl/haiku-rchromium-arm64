#!/bin/sh
# Is PartitionAlloc's BackupRefPtr the thing corrupting AstRawStrings?
#
# Run against repro2.html rather than x.com. repro.html crashed 3 of 10 on
# 2026-09-22 against x.com's 7 of 10 in the same interleaved run, which
# settles that a locally served page does reproduce this -- but 3 in 10 is a
# weak control. repro2.html keeps four <script src> in flight for the whole
# run so background streaming parses never stop, which is what repro.html
# only did for its first few seconds. The baseline column of this run is
# also the measurement of whether that helped.
#
# This build has PA_BUILDFLAG(USE_PARTITION_ALLOC_AS_MALLOC)=1 and
# USE_RAW_PTR_BACKUP_REF_IMPL=1, so malloc here is PartitionAlloc and every
# raw_ptr<T> goes through BackupRefPtr. That matters for this crash for two
# reasons. V8's AstRawStringMap is a plain malloc'd array
# (base::DefaultAllocationPolicy), so the map whose keys come back wrong is
# PartitionAlloc memory, while the AstRawStrings the keys should point at are
# in a Zone. And BRP decides whether a pointer belongs to it by testing the
# address against PartitionAddressSpace's reserved pools -- a many-gigabyte
# PROT_NONE reservation this port has never checked Haiku's mmap actually
# honours. A pool test that answers wrongly makes raw_ptr apply refcount
# writes to memory PartitionAlloc does not own.
#
# Every native test run against this crash so far (malloc concurrency, mmap
# reservations, memory ordering) was built with the plain Haiku toolchain and
# therefore exercised libroot's allocator, not this one. The allocator the
# browser actually uses has not been tested at all.
#
# ENABLE_BACKUP_REF_PTR_FEATURE_FLAG is 1 in this build, so BRP is runtime
# switchable and this needs no rebuild.
LIMIT=${1:-70}
[ -n "$2" ] && date "$2" > /dev/null
OUT=/boot/home/r2brp.txt
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
    log=/boot/home/r2b$N.log
    killcs
    cd /xfer2 || exit 1
    export LIBRARY_PATH=/boot/home/cs/lib:/boot/system/lib
    ./content_shell --ozone-platform=haiku --no-sandbox --single-process \
        --disable-gpu --in-process-gpu --disable-gpu-compositing \
        --content-shell-host-window-size=1000x700 $1 \
        http://10.0.2.2:8000/repro2.html > "$log" 2>&1 &
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

# Interleaved, so a drift in the machine's state lands on both arms. Three
# runs per arm proved nothing last time and six barely separated 1/6 from 3/6;
# ten each is the minimum that can tell 100% from 60%.
BASE=""
NOBRP=""
k=0
while [ "$k" -lt 10 ]; do
    one ""; BASE="$BASE$V"
    one "--disable-features=PartitionAllocBackupRefPtr"; NOBRP="$NOBRP$V"
    k=$((k + 1))
    printf 'baseline  %s\nno-brp    %s\n' "$BASE" "$NOBRP" > "$OUT"
done
printf 'baseline  %s\nno-brp    %s\nX = crashed, . = survived\n---- done ----\n' \
    "$BASE" "$NOBRP" > "$OUT"
