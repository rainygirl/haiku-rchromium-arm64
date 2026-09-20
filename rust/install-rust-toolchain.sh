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
HOST="${RUST_HOST_TRIPLE:-$(uname -m)-unknown-linux-gnu}"
# stage2 when it is there: its rustc internals are compiled by stage1, i.e. by
# a compiler of the same version, which is what crubit's cc_bindings_from_rs
# needs to link against (stage1's own internals come from the stage0 beta and
# are rejected as "compiled by an incompatible version of rustc").
STAGE="$RB/rust/build/$HOST/stage2"
[ -x "$STAGE/bin/rustc" ] || STAGE="$RB/rust/build/$HOST/stage1"
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

# The rustc-dev component: the rustc_* crates as rlibs. x.py leaves them in
# the build tree rather than the sysroot, and cc_bindings_from_rs (crubit) is
# built against them. Same stage as the compiler above, so the versions agree.
RUSTC_ROOT="$(dirname "$STAGE")/$(basename "$STAGE")-rustc"
RUSTC_BUILD="$RUSTC_ROOT/$HOST/release"
if [ -d "$RUSTC_BUILD/build" ]; then
	DEV="$TP/rust-toolchain/lib/rustlib/$HOST/lib"
	mkdir -p "$DEV"
	# Everything the compiler crates were built against, not just the
	# rustc_* ones: rustc_driver's own dependency list names the vendored
	# crates (derive_where, anstream, ...) and rustc refuses to load it
	# without them.
	# .so as well as .rlib: rustc_driver is only ever built as a dylib, and
	# with just its .rmeta in the sysroot every `extern crate rustc_driver`
	# fails with "required to be available in rlib format".
	find "$RUSTC_BUILD/build" -maxdepth 4 \
		\( -name "lib*.rlib" -o -name "lib*.rmeta" -o -name "lib*.so" \) \
		-exec cp -n {} "$DEV/" \; 2>/dev/null || true
	find "$RUSTC_BUILD/deps" -maxdepth 1 \
		\( -name "*.rlib" -o -name "*.rmeta" \) \
		-exec cp -n {} "$DEV/" \; 2>/dev/null || true
	# The proc macros the compiler crates use are host dylibs and sit in the
	# build tree beside the target directory rather than inside it.
	find "$RUSTC_ROOT/release/build" -maxdepth 5 -name "lib*.so" \
		-exec cp -n {} "$DEV/" \; 2>/dev/null || true
	echo "  rustc-dev: $(ls "$DEV" | grep -c '^librustc_') rustc_* files"
fi

# rustfmt is a tool, not compiler output, and x.py puts it beside the stage
# rather than in it -- and at whichever stage built it, which is stage1 even
# when the compiler above is stage2. run_bindgen.py formats every generated
# binding with it, and the bundle's copy is an x86_64 binary.
for d in "$(dirname "$STAGE")/$(basename "$STAGE")-tools-bin" \
         "$(dirname "$STAGE")/stage2-tools-bin" \
         "$(dirname "$STAGE")/stage1-tools-bin"; do
	[ -x "$d/rustfmt" ] && cp -f "$d/rustfmt" "$TP/rust-toolchain/bin/rustfmt" &&
		break
done
# rustfmt is linked against the driver of the stage that built it, which is
# not the stage the compiler comes from, so both dylibs have to be here or it
# dies with "librustc_driver-....so: cannot open shared object file".
cp -n "$(dirname "$STAGE")"/stage*/lib/librustc_driver*.so \
      "$TP/rust-toolchain/lib/" 2>/dev/null || true
# cargo comes from the downloaded stage0: x.py does not build one here.
[ -x "$(dirname "$STAGE")/stage0/bin/cargo" ] &&
	cp -f "$(dirname "$STAGE")/stage0/bin/cargo" "$TP/rust-toolchain/bin/cargo"

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

# bindgen and crubit's cc_bindings_from_rs come from the bundle as x86_64
# binaries, so on an arm64 host they have to be the ones built here by
# tools/rust/build_bindgen.py and tools/rust/build_crubit.py. The bundle's
# copies were just laid down by the -n copy above; ours replace them.
for tool in bindgen:bindgen-host-build cc_bindings_from_rs:crubit-build; do
	name="${tool%%:*}"
	built="$(ls "$TP/rust-toolchain-intermediate/${tool##*:}/$HOST/release/$name" \
		/work/crubit-build*/target/release/"$name" 2>/dev/null | head -1)"
	[ -n "$built" ] && cp -f "$built" "$TP/rust-toolchain/bin/$name" &&
		echo "  $name: $built"
done

echo "  installed: $("$TP/rust-toolchain/bin/rustc" --version)"
echo "  Haiku targets: $("$TP/rust-toolchain/bin/rustc" --print target-list | grep -c haiku)"
