#!/bin/bash
# Put both allocators on the transfer disk at once.
#
# The PartitionAlloc question cannot be answered by measuring one build today
# against another build yesterday: x.com's own crash rate moved 10/10 -> 3/6
# -> 7/10 across three days, and even the local page sits somewhere between 3
# and 4 in ten. The only measurement worth taking is interleaved, which means
# both binaries have to be reachable in one boot. They are 323 MB each; the
# M4 has 156 GB free, so the 700 MB transfer disk simply becomes 1.4 GB.
#
# /xfer2/content_shell        PartitionAlloc (the shipping configuration)
# /xfer2/nopa/content_shell   use_partition_alloc_as_malloc = false
set -e
cd ~/rtwitter-test
export PATH=$PATH:/usr/local/bin
P=/Users/rainygirl/Workspace/github/rreader/rreader-python/venv/bin/python3
FILES="content_shell content_shell.pak snapshot_blob.bin v8_context_snapshot.bin libtest_trace_processor.so icudtl.dat"

echo "== pulling the no-PartitionAlloc build =="
mkdir -p cs-nopa cs-nopa/lib
for f in $FILES; do
    docker cp haiku-chromium:/work/chromium/src/out/haiku-arm64-nopa/$f cs-nopa/
done
# The shim is built per-out-directory too; take the matching one.
docker cp haiku-chromium:/work/chromium/src/out/haiku-arm64-nopa/libchromium_haiku.so cs-nopa/lib/ 2>/dev/null \
    || cp cs-dcheck/lib/libchromium_haiku.so cs-nopa/lib/ 2>/dev/null \
    || echo "NOTE: no shim copied; the guest's /boot/home/cs/lib one will be used"
ls -la cs-nopa/content_shell

echo "== shutting the guest down =="
if pgrep -f qemu-system-aarch64 >/dev/null; then
    SHOTDIR=/tmp KEYDELAY=0.12 $P shot.py /tmp/rtw.qmp text "sync; shutdown" || true
    $P shot.py /tmp/rtw.qmp key ret || true
    sleep 25
    $P - <<'PY' || true
import socket, json
s=socket.socket(socket.AF_UNIX); s.connect("/tmp/rtw.qmp"); f=s.makefile("rw"); f.readline()
def cmd(c):
    f.write(json.dumps(c)+"\n"); f.flush()
    try:
        while True:
            line=f.readline()
            if not line: return
            m=json.loads(line)
            if "return" in m or "error" in m: return m
    except Exception: return
cmd({"execute":"qmp_capabilities"}); cmd({"execute":"quit"})
PY
    sleep 5
fi
pgrep -f qemu-system-aarch64 >/dev/null && { echo "QEMU still running -- aborting"; exit 1; }

echo "== rebuilding xfer2.img at 1.4 GB =="
rm -f xfer2.img
mkfile -n 1400m xfer2.img
DEV=$(hdiutil attach -imagekey diskimage-class=CRawDiskImage -nomount xfer2.img 2>/dev/null | head -1 | awk '{print $1}')
newfs_msdos -F 32 -v XFER2 "$DEV" >/dev/null 2>&1
diskutil mount "$DEV" >/dev/null
cp cs-dcheck/* /Volumes/XFER2/ 2>/dev/null || true
mkdir -p /Volumes/XFER2/nopa
cp cs-nopa/* /Volumes/XFER2/nopa/ 2>/dev/null || true
cp -R cs-nopa/lib /Volumes/XFER2/nopa/ 2>/dev/null || true
sync
ls -la /Volumes/XFER2/content_shell /Volumes/XFER2/nopa/content_shell
df -h /Volumes/XFER2 | tail -1
diskutil unmount "$DEV" >/dev/null
hdiutil detach "$DEV" >/dev/null

echo "== booting the guest =="
: > serial-w.log
nohup /opt/homebrew/bin/qemu-system-aarch64 -M virt -cpu host -accel hvf -smp 4 -m 3072 \
  -bios /opt/homebrew/share/qemu/edk2-aarch64-code.fd \
  -device qemu-xhci,id=usb \
  -drive file=renku.image,if=none,id=drv0,format=raw -device usb-storage,bus=usb.0,drive=drv0 \
  -device ahci,id=ahci \
  -drive file=xfer2.img,if=none,id=drv1,format=raw -device ide-hd,bus=ahci.0,drive=drv1 \
  -device usb-kbd,bus=usb.0 -device usb-tablet,bus=usb.0 \
  -netdev user,id=n0,hostfwd=tcp:127.0.0.1:2231-:22 -device virtio-net-pci,netdev=n0 \
  -device ramfb -display none -qmp unix:/tmp/rtw.qmp,server,nowait \
  -serial file:serial-w.log > qemu-dcheck.out 2>&1 &
sleep 100
pgrep -f qemu-system-aarch64 >/dev/null && echo "QEMU RUNNING" || { echo FAILED; cat qemu-dcheck.out; exit 1; }
