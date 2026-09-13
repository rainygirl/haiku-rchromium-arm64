#!/bin/bash
#
# Build everything the Chromium arm64 port needs so far, and leave the
# packages where the image build picks them up.
#
#   1. the cross sysroot           (make-sysroot.sh)
#   2. Python's missing libraries  (build-pydeps-arm64.sh)
#   3. Python 3.14                 (build-python-arm64.sh, package-python-arm64.sh)
#   4. gn and ninja                (build-gn-ninja-arm64.sh)
#
# Runs inside the haiku-builder container. Each step is skipped if its output
# is already there, so this is safe to re-run.
#
set -e
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
G="${RENKU_GEN:-/root/gen-kd}"
TREE="${RENKU_TREE:-/root/haiku-arm64}"
PKGDIR="$TREE/data/renku-packages"

mkdir -p "$PKGDIR"

step() { printf '\n########## %s\n' "$*"; }

step "Python 3.14 and its libraries"
"$HERE/build-python-arm64.sh"        # assembles the sysroot as part of its work
"$HERE/build-pydeps-arm64.sh"
# Rebuild Python now that ssl, sqlite, lzma, bz2 and readline are available;
# the first pass configured without them.
"$HERE/cross-configure.sh"
( cd "${PYBUILD_DIR:-/root/pybuild}/build-arm64" && make -j"${JOBS:-8}" )
"$HERE/package-python-arm64.sh" "$PKGDIR/python3.14-3.14.7-1-arm64.hpkg"

step "gn and ninja"
"$HERE/build-gn-ninja-arm64.sh" "$PKGDIR/gn_ninja-1.12.1-1-arm64.hpkg"

step "clang and lld"
# The long one -- a couple of hours. Set RENKU_SKIP_LLVM=1 to leave it out.
if [ "${RENKU_SKIP_LLVM:-0}" != 1 ]; then
	"$HERE/build-llvm-arm64.sh" "$PKGDIR/llvm_clang-19.1.7-1-arm64.hpkg"
else
	echo "  skipped (RENKU_SKIP_LLVM=1)"
fi

step "done"
ls -lh "$PKGDIR"
echo
echo "The image build picks these up through RENKU_LOCAL_PACKAGES;"
echo "build-renku-arm64.sh sets that."
