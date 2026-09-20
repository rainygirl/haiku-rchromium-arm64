#!/bin/bash
#
# Build crubit's cc_bindings_from_rs for an arm64 Linux host.
#
# Chromium ships it as an x86_64 binary in the rust-toolchain bundle, so on an
# Apple Silicon container there is nothing to run; and since it links rustc's
# internals it can only be built against the very rustc whose metadata it will
# read -- the one ../rust/build-rust-arm64.sh produces (stage2, so that the
# internals come from a compiler of the same version).
#
# Two deviations from tools/rust/build_crubit.py, both required here:
#   * crubit HEAD, not the pinned revision: the pinned one does not compile
#     against a current nightly (rustc internals drift, e.g. a new DefKind
#     variant makes a match non-exhaustive).
#   * -Cprefer-dynamic: rustc_driver only ever exists as a dylib, so a
#     statically linked binary stops with "required to be available in rlib
#     format".
set -e
SRC="${1:-/work/chromium/src}"
OUT="${CRUBIT_BUILD_DIR:-/work/crubit-build}"
TP="$SRC/third_party"
CRUBIT_SRC="$TP/rust-toolchain-intermediate/crubit"

[ -d "$CRUBIT_SRC" ] || (cd "$SRC" && python3 tools/rust/build_crubit.py \
	--crubit-force-head-revision --out-dir "$OUT" || true)

cd "$SRC"
export CARGO_HOME="$OUT/target/cargo_home"
export RUSTC="$TP/rust-toolchain/bin/rustc"
export RUSTFLAGS="-Cprefer-dynamic -Clink-args=-Wl,-z,origin -Clink-args=-Wl,-rpath,\$ORIGIN/../lib"
export LD_LIBRARY_PATH="$TP/rust-toolchain/lib"
"$TP/rust-toolchain/bin/cargo" build --release --locked \
	--bin cc_bindings_from_rs \
	--target-dir "$OUT/target" \
	--manifest-path "$CRUBIT_SRC/cargo/cc_bindings_from_rs/cc_bindings_from_rs/Cargo.toml"

cp -f "$OUT/target/release/cc_bindings_from_rs" "$TP/rust-toolchain/bin/"
mkdir -p "$TP/rust-toolchain/lib/third_party/crubit"
for i in BUILD.gn LICENSE crubit.gni support; do
	cp -a "$CRUBIT_SRC/$i" "$TP/rust-toolchain/lib/third_party/crubit/" 2>/dev/null || true
done
echo "  installed: $("$TP/rust-toolchain/bin/cc_bindings_from_rs" --version 2>/dev/null || echo cc_bindings_from_rs)"
