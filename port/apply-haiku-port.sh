#!/bin/bash
#
# Apply the Haiku port to a Chromium checkout.
#
# Step 4 of the arm64 work. Chromium has no Haiku support of any kind: of
# 505,289 files in the tree, 13 mention Haiku and every one of those is inside
# a vendored Rust crate. This is the scaffolding that has to exist before any
# of it can be built -- platform detection, a target OS, a toolchain.
#
# Re-runnable: each step checks whether it has already been done.
#
set -e
SRC="${1:-/haiku-build/chromium/src}"
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

[ -d "$SRC/build/config" ] || {
	echo "not a Chromium checkout: $SRC" >&2
	exit 1
}

echo "Applying the Haiku port to $SRC"

# 1. Platform detection: turn __HAIKU__ into OS_HAIKU and BUILDFLAG(IS_HAIKU),
#    and put Haiku in the OS_POSIX set.
python3 "$HERE/port-build-config.py" "$SRC/build/build_config.h"

# 2. A target the build system recognises.
python3 "$HERE/port-buildconfig-gn.py" "$SRC/build/config/BUILDCONFIG.gn"

# 3. A Rust ABI triple. Chromium's Rust cannot be switched off -- skia's
#    bridge_rust_side is a hard dependency -- so the target has to have one.
python3 "$HERE/port-rust-gni.py" "$SRC"

# 4. Source fixes: platform lists, POSIX facilities Haiku spells differently,
#    the message pump, crubit. Order matters only in that port-rust-gni.py
#    must precede port-crubit.py -- both edit build/config/rust.gni.
python3 "$HERE/port-feature-flags.py" "$SRC"
python3 "$HERE/port-base-posix.py" "$SRC"
python3 "$HERE/port-message-pump.py" "$SRC"
python3 "$HERE/port-perfetto-os-lists.py" "$SRC"
# These were written but never wired in here, so a clean checkout came out
# missing every edit they carry -- //content, //net, //v8 and the libc crate's
# Haiku arm64 source list.
python3 "$HERE/port-content.py" "$SRC"
python3 "$HERE/port-net.py" "$SRC"
python3 "$HERE/port-v8.py" "$SRC"
python3 "$HERE/port-rust-libc.py" "$SRC"
python3 "$HERE/port-crubit.py" "$SRC"
python3 "$HERE/port-content-shell-ui.py" "$SRC"
python3 "$HERE/port-content-shell-build.py" "$SRC"

# 5. The toolchain and config files, which have no upstream counterpart to
#    patch and are simply added.
for f in $(cd "$HERE/files" && find . -type f); do
	mkdir -p "$SRC/$(dirname "${f#./}")"
	cp "$HERE/files/${f#./}" "$SRC/${f#./}"
	echo "  added ${f#./}"
done

cat <<'USAGE'

Done. Configure with:

  gn gen out/haiku-arm64 --args='
      target_os="haiku"
      target_cpu="arm64"
      is_debug=false
      symbol_level=0
      haiku_sysroot="/root/pybuild/sysroot"
  '
USAGE
