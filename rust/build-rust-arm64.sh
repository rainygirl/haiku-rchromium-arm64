#!/bin/bash
#
# Add aarch64-unknown-haiku to rustc and build a std for it.
#
# Rust ships Haiku targets for i686 and x86_64 only. Chromium needs one for
# arm64 and cannot do without Rust at all -- enable_rust=false fails at
# //skia:bridge_rust_side, a hard dependency of the browser -- so this target
# has to exist before any Chromium work on arm64 can proceed.
#
set -e
RB="${RUSTBUILD_DIR:-/root/rustbuild}"
CT=/root/gen-arm64/cross-tools-arm64/bin/aarch64-unknown-haiku
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
JOBS="${JOBS:-8}"

command -v curl >/dev/null || {
	echo "curl is required (rustc's bootstrap downloads stage0 with it)" >&2
	exit 1
}

mkdir -p "$RB"
cd "$RB"

echo "=== source"
[ -d rust ] || git clone --depth 1 https://github.com/rust-lang/rust.git

echo "=== target spec"
python3 "$HERE/apply-rust-haiku-arm64.py" "$RB/rust"

echo "=== configuring"
cd "$RB/rust"
cat > bootstrap.toml <<EOF
change-id = "ignore"

# Only what is needed to produce a std for a new Tier 3 target.
profile = "library"

[llvm]
# Do not build LLVM. rustc here is only a means to cross-compile std, and the
# CI build is both correct for this commit and about two hours cheaper.
download-ci-llvm = true

[build]
target = ["aarch64-unknown-haiku"]
docs = false
extended = false

[rust]
channel = "nightly"
debug = false
debuginfo-level = 0

[target.aarch64-unknown-haiku]
cc = "$CT-gcc"
cxx = "$CT-g++"
ar = "$CT-ar"
ranlib = "$CT-ranlib"
linker = "$CT-gcc"
EOF

echo "=== building std"
# The stage0 compiler is a released beta and does not know the new target, so
# its sanity check refuses the build. The check exists to catch typos in a
# custom target name; here the name is deliberately new. The error message
# names this variable itself.
export BOOTSTRAP_SKIP_TARGET_SANITY=1
python3 x.py build --stage 1 library/std --target aarch64-unknown-haiku -j "$JOBS"

RUSTC="$RB/rust/build/x86_64-unknown-linux-gnu/stage1/bin/rustc"
echo
echo "Built. Use it with:"
echo "  $RUSTC --target aarch64-unknown-haiku -C linker=$CT-gcc ..."
echo
"$RUSTC" --print target-list | grep haiku | sed 's/^/  /'
