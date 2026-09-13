#!/bin/bash
# Assemble a cross sysroot for building third-party software against Haiku
# arm64. There is no prebuilt one: the cross toolchain ships no sysroot, the
# Haiku headers and libraries live in the build output, and the third-party
# libraries only ever exist as downloaded .hpkg files.
set -e
G="${RENKU_GEN:-/root/gen-kd}"
ROOT="${SYSROOT:-/root/pybuild/sysroot}"
SR=$ROOT/boot/system/develop
P=$G/objects/haiku/arm64/packaging/packages_build/minimum
PKG=$(find "$G/objects/linux" -name package -type f -perm -u+x 2>/dev/null | head -1)
[ -n "$PKG" ] || { echo "no package tool under $G/objects/linux" >&2; exit 1; }

rm -rf "$ROOT"
# Both directories matter: a Haiku package puts its runtime libraries in
# boot/system/lib and leaves boot/system/develop/lib holding symlinks that
# point at them through ../../lib. Skip boot/system/lib and every one of
# those symlinks dangles, and the linker reports "cannot find -lz".
mkdir -p "$SR/lib" "$ROOT/boot/system/lib"

# Headers and the startup objects (crti.o and friends) come from the staged
# haiku_devel package, which is laid out exactly like a real Haiku system.
cp -a "$P/hpkg_-haiku_devel.hpkg/contents/develop/headers" "$SR/headers"
cp -a "$P/hpkg_-haiku_devel.hpkg/contents/develop/lib/." "$SR/lib/"

# Haiku's own libraries are not in any package here -- they are build output --
# so the devel package's symlinks for them have nothing to point at. Replace
# each with the real library jam produced.
for l in $(find "$SR/lib" -maxdepth 1 -xtype l); do
	n=$(basename "$l")
	f=$(find "$G/objects/haiku/arm64/release" -name "$n" -type f 2>/dev/null | head -1)
	rm -f "$l"
	[ -n "$f" ] && cp "$f" "$l"
done

# libstdc++/libsupc++ from the bootstrap gcc package -- runtime libraries to
# boot/system/lib, the link-time symlinks and archives to develop/lib, for the
# same reason as above.
for d in "$G"/build_packages/gcc_syslibs-*-arm64/lib; do
	[ -d "$d" ] && cp -a "$d"/. "$ROOT/boot/system/lib/" 2>/dev/null || true
done
for d in "$G"/build_packages/gcc_syslibs_devel-*-arm64/develop/lib; do
	[ -d "$d" ] && cp -a "$d"/. "$SR/lib/" 2>/dev/null || true
done

# The third-party libraries Python and friends link against. jam only unpacks
# what the image itself needs, so take these straight out of the downloads.
STAGE=$(mktemp -d)
for p in zlib zlib_devel libffi libffi_devel ncurses6 ncurses6_devel \
         expat expat_devel icu74 icu74_devel; do
	f=$(echo "$G"/download/$p-*.hpkg | cut -d' ' -f1)
	[ -f "$f" ] || { echo "  missing: $p"; continue; }
	rm -rf "$STAGE/x" && mkdir -p "$STAGE/x"
	( cd "$STAGE/x" && "$PKG" extract "$f" >/dev/null 2>&1 )
	[ -d "$STAGE/x/develop/headers" ] && cp -an "$STAGE/x/develop/headers"/. "$SR/headers/" 2>/dev/null || true
	[ -d "$STAGE/x/develop/lib" ]     && cp -an "$STAGE/x/develop/lib"/.     "$SR/lib/"     2>/dev/null || true
	[ -d "$STAGE/x/lib" ]             && cp -an "$STAGE/x/lib"/.  "$ROOT/boot/system/lib/"  2>/dev/null || true
	echo "  + $p"
done
rm -rf "$STAGE"

left=$(find "$SR/lib" -maxdepth 1 -xtype l | wc -l)
[ "$left" -eq 0 ] || echo "warning: $left dangling symlinks left in develop/lib"
# The cross gcc was configured with --with-sysroot pointing here; making that
# path real is what lets every later build work with no -I, -B or -L at all.
ln -sfn "$ROOT" /root/gen-arm64/cross-tools-arm64/sysroot

echo "sysroot ready at $ROOT"
