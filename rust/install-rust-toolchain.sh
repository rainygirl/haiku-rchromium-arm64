#!/bin/bash
#
# Point Chromium at the rustc that knows aarch64-unknown-haiku.
#
# Chromium bundles its own Rust in //third_party/rust-toolchain, and that one
# only has the i686 and x86_64 Haiku targets. ../rust/ builds one with the
# arm64 target added; this swaps it in.
#
# Only the compiler and its libraries come from our build. bindgen, clippy,
# rustdoc, cargo and the crubit support files are Chromium's own build tools,
# not compiler output, so they stay from the bundle.
#
set -e
SRC="${1:-/haiku-build/chromium/src}"
RB="${RUSTBUILD_DIR:-/root/rustbuild}"
STAGE="$RB/rust/build/x86_64-unknown-linux-gnu/stage1"
TP="$SRC/third_party"

[ -x "$STAGE/bin/rustc" ] || {
	echo "no rustc at $STAGE -- run ../rust/build-rust-arm64.sh first" >&2
	exit 1
}
"$STAGE/bin/rustc" --print target-list | grep -qx aarch64-unknown-haiku || {
	echo "that rustc does not know aarch64-unknown-haiku" >&2
	exit 1
}

if [ ! -d "$TP/rust-toolchain.orig" ]; then
	mv "$TP/rust-toolchain" "$TP/rust-toolchain.orig"
	echo "  kept the bundled toolchain as rust-toolchain.orig"
fi

rm -rf "$TP/rust-toolchain"
mkdir -p "$TP/rust-toolchain"
cp -a "$STAGE/bin" "$TP/rust-toolchain/"
cp -a "$STAGE/lib" "$TP/rust-toolchain/"

# Everything our build does not produce comes from the bundle: the build
# tools in bin/, the crubit support BUILD.gn under lib/third_party, and the
# etc/libexec/share trees.
cp -an "$TP/rust-toolchain.orig/bin/." "$TP/rust-toolchain/bin/" 2>/dev/null || true
# Those tools link the bundle's own rustc driver by soname. Ours has a
# different hash, so both have to be present or rustfmt dies with
# "librustc_driver-....so: cannot open shared object file".
cp -n "$TP/rust-toolchain.orig/lib"/librustc_driver*.so "$TP/rust-toolchain/lib/" 2>/dev/null || true
cp -n "$TP/rust-toolchain.orig/lib"/libstd-*.so "$TP/rust-toolchain/lib/" 2>/dev/null || true
cp -an "$TP/rust-toolchain.orig/lib/third_party" "$TP/rust-toolchain/lib/" 2>/dev/null || true
# The vendored crate sources Chromium builds its own host tools from. A
# rustc built by x.py does not ship them.
cp -an "$TP/rust-toolchain.orig/lib/rustlib/src/rust/library/vendor" \
       "$TP/rust-toolchain/lib/rustlib/src/rust/library/" 2>/dev/null || true
for d in etc libexec share VERSION; do
	[ -e "$TP/rust-toolchain.orig/$d" ] &&
		cp -an "$TP/rust-toolchain.orig/$d" "$TP/rust-toolchain/" 2>/dev/null || true
done

echo "  installed: $("$TP/rust-toolchain/bin/rustc" --version)"
echo "  Haiku targets: $("$TP/rust-toolchain/bin/rustc" --print target-list | grep -c haiku)"
