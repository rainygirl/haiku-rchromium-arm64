#!/bin/bash
#
# Cross-build clang and lld for Haiku arm64.
#
# Step 3 of the Chromium arm64 port. gn and ninja from step 2 both run on the
# target, but the image has no compiler for them to drive -- a gn+ninja build
# there stops at "gcc: command not found". This supplies one.
#
# LLVM already knows Haiku: it has a Haiku triple and clang ships a Haiku
# toolchain driver (clang/lib/Driver/ToolChains/Haiku.cpp). What it does not
# have is a way to build itself for a target it cannot run on, so this is the
# usual two-stage arrangement: build the tablegen tools for the host, then
# cross-build everything else against them.
#
set -e
LB="${LLVMBUILD_DIR:-/root/llvmbuild}"
PB="${PYBUILD_DIR:-/root/pybuild}"
G="${RENKU_GEN:-/root/gen-kd}"
GB="${GNBUILD_DIR:-/root/gnbuild}"
CT=/root/gen-arm64/cross-tools-arm64/bin/aarch64-unknown-haiku
# CMake's find_package does not consult the compiler's sysroot, and Haiku's
# layout is develop/headers and develop/lib rather than include and lib, so
# the few libraries LLVM looks for have to be pointed at by hand.
SR="$PB/sysroot/boot/system/develop"
VER=19.1.7
SRC="$LB/llvm-project-$VER.src"
# Compiling clang's AST sources takes well over a gigabyte per cc1plus, so on
# a 7 GB container eight of them at once gets one killed:
#   aarch64-unknown-haiku-g++: fatal error: Killed signal terminated program cc1plus
# Four is what fits. Raise it if the machine has more memory -- this is about
# RAM, not cores.
JOBS="${LLVM_JOBS:-4}"
# Links are worse again; two at a time is the most that fits.
LINK_JOBS="${LINK_JOBS:-2}"
NINJA="$GB/ninja-host/ninja"
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PKG=$(find "$G/objects/linux" -name package -type f -perm -u+x 2>/dev/null | head -1)

log() { printf '\n=== %s\n' "$*"; }

command -v cmake >/dev/null || { echo "cmake is required" >&2; exit 1; }
[ -x "$NINJA" ] || { echo "no host ninja at $NINJA -- run build-gn-ninja-arm64.sh first" >&2; exit 1; }

ln -sfn "$PB/sysroot" /root/gen-arm64/cross-tools-arm64/sysroot

mkdir -p "$LB"
cd "$LB"

log "source"
if [ ! -d "$SRC" ]; then
	[ -f llvm.tar.xz ] || wget -q \
		"https://github.com/llvm/llvm-project/releases/download/llvmorg-$VER/llvm-project-$VER.src.tar.xz" \
		-O llvm.tar.xz
	tar xJf llvm.tar.xz
fi

log "patching the Haiku driver"
# clang links with lld by default, and lld's AArch64 defaults produce an image
# Haiku's runtime_loader will not map. See the comment the patch inserts.
python3 "$HERE/patch-haiku-driver.py" \
	"$SRC/clang/lib/Driver/ToolChains/Haiku.cpp"

# --- stage 1: the tablegen tools, for the host --------------------------
log "host tablegen"
if [ ! -x "$LB/build-host/bin/llvm-tblgen" ] || [ ! -x "$LB/build-host/bin/clang-tblgen" ]; then
	rm -rf "$LB/build-host"
	mkdir -p "$LB/build-host"
	cd "$LB/build-host"
	cmake -G Ninja "$SRC/llvm" \
		-DCMAKE_BUILD_TYPE=Release \
		-DLLVM_ENABLE_PROJECTS="clang" \
		-DLLVM_TARGETS_TO_BUILD=AArch64 \
		-DLLVM_ENABLE_ASSERTIONS=OFF \
		-DCMAKE_MAKE_PROGRAM="$NINJA"
	# The host stage is much lighter and can use every core.
	"$NINJA" -j"${JOBS_HOST:-8}" llvm-tblgen clang-tblgen llvm-config
	cd "$LB"
fi

# --- stage 2: clang and lld, for the target -----------------------------
log "cross-building clang and lld"
rm -rf "$LB/build-arm64"
mkdir -p "$LB/build-arm64"
cd "$LB/build-arm64"

# CMAKE_SYSROOT is deliberately not set. The cross gcc already knows Haiku's
# header layout through its own --with-sysroot, and pointing CMake at the
# sysroot instead makes it look for $sysroot/usr/include, which a Haiku tree
# does not have.
cmake -G Ninja "$SRC/llvm" \
	-DCMAKE_MAKE_PROGRAM="$NINJA" \
	-DCMAKE_BUILD_TYPE=Release \
	-DCMAKE_SYSTEM_NAME=Haiku \
	-DCMAKE_SYSTEM_PROCESSOR=aarch64 \
	-DCMAKE_C_COMPILER="$CT-gcc" \
	-DCMAKE_CXX_COMPILER="$CT-g++" \
	-DCMAKE_AR="$CT-ar" \
	-DCMAKE_RANLIB="$CT-ranlib" \
	-DCMAKE_C_FLAGS="-D_DEFAULT_SOURCE" \
	-DCMAKE_CXX_FLAGS="-D_DEFAULT_SOURCE" \
	-DCMAKE_INSTALL_PREFIX=/boot/system \
	-DLLVM_ENABLE_PROJECTS="clang;lld" \
	-DLLVM_TARGETS_TO_BUILD=AArch64 \
	-DLLVM_DEFAULT_TARGET_TRIPLE=aarch64-unknown-haiku \
	-DLLVM_HOST_TRIPLE=aarch64-unknown-haiku \
	-DLLVM_TABLEGEN="$LB/build-host/bin/llvm-tblgen" \
	-DCLANG_TABLEGEN="$LB/build-host/bin/clang-tblgen" \
	-DLLVM_CONFIG_PATH="$LB/build-host/bin/llvm-config" \
	-DLLVM_ENABLE_ASSERTIONS=OFF \
	-DLLVM_INCLUDE_TESTS=OFF \
	-DLLVM_INCLUDE_BENCHMARKS=OFF \
	-DLLVM_INCLUDE_EXAMPLES=OFF \
	-DLLVM_INCLUDE_DOCS=OFF \
	-DCLANG_INCLUDE_TESTS=OFF \
	-DCLANG_ENABLE_STATIC_ANALYZER=OFF \
	-DCLANG_ENABLE_ARCMT=OFF \
	-DLLVM_ENABLE_LIBXML2=OFF \
	-DLLVM_ENABLE_ZSTD=OFF \
	-DLLVM_ENABLE_TERMINFO=OFF \
	-DLLVM_ENABLE_LIBEDIT=OFF \
	-DLLVM_ENABLE_ZLIB=FORCE_ON \
	-DZLIB_INCLUDE_DIR="$SR/headers" \
	-DZLIB_LIBRARY="$SR/lib/libz.so" \
	-DCMAKE_INCLUDE_PATH="$SR/headers" \
	-DCMAKE_LIBRARY_PATH="$SR/lib" \
	-DLLVM_BUILD_LLVM_DYLIB=ON \
	-DLLVM_LINK_LLVM_DYLIB=ON \
	-DCLANG_LINK_CLANG_DYLIB=ON \
	-DLLVM_PARALLEL_LINK_JOBS="$LINK_JOBS"

# CLANG_ENABLE_STATIC_ANALYZER=OFF keeps the analyzer out of the clang
# binary, but in LLVM 19 clang/lib/CMakeLists.txt still does an unconditional
# add_subdirectory(StaticAnalyzer), so the checkers are compiled either way.
# Only the ARC migrator actually drops out -- about a hundred targets. Both
# options are set because they cost nothing, not because they save much.
"$NINJA" -j"$JOBS"

log "staging"
ST="$LB/stage"
rm -rf "$ST"
DESTDIR="$ST" "$NINJA" install

# The install brings in every tool LLVM builds; the image only needs a
# working compiler and linker. Trimming takes this from well over 1 GB to
# something an ISO can carry.
B="$ST/boot/system/bin"
# Several of these are symlinks to a different name -- llvm-readelf to
# llvm-readobj, llvm-ranlib and llvm-dlltool to llvm-ar, llvm-strip to
# llvm-objcopy -- so the target has to be kept too or the link dangles and the
# tool reports "command not found".
KEEP="clang clang++ clang-19 clang-cpp ld.lld lld lld-link
      llvm-ar llvm-ranlib llvm-nm llvm-objdump llvm-objcopy llvm-strip
      llvm-readobj llvm-readelf llvm-size llvm-strings llvm-dwarfdump
      llvm-cxxfilt llvm-symbolizer llvm-addr2line"
for f in "$B"/*; do
	n=$(basename "$f")
	keep=no
	for k in $KEEP; do [ "$n" = "$k" ] && keep=yes; done
	[ "$keep" = yes ] || rm -f "$f"
done
rm -rf "$ST/boot/system/lib/cmake" "$ST/boot/system/share" \
       "$ST/boot/system/include" "$ST/boot/system/libexec"
# The static archives are only useful for building against LLVM, which is not
# what this package is for; the tools all link the dylib.
find "$ST/boot/system/lib" -name '*.a' -delete

# libclang is the C API, libLTO the linker plugin, libRemarks the diagnostics
# reader. Nothing kept above links any of them -- the tools use libclang-cpp
# and libLLVM -- and libclang alone is 37 MB.
rm -f "$ST/boot/system/lib"/libclang.so* \
      "$ST/boot/system/lib"/libLTO.so* \
      "$ST/boot/system/lib"/libRemarks.so*
# lib/clang/19/include is clang's own resource directory -- stddef.h,
# stdarg.h, the intrinsics headers. clang cannot compile anything without it,
# so it stays.

STRIP="$CT-strip"
find "$ST" -type f \( -perm -u+x -o -name '*.so*' \) \
	-exec "$STRIP" --strip-unneeded {} \; 2>/dev/null || true

log "packaging"
mkdir -p "$ST/boot/system/data/licenses"
cp "$SRC/llvm/LICENSE.TXT" "$ST/boot/system/data/licenses/Apache v2 with LLVM Exceptions"

cat > "$ST/boot/system/.PackageInfo" <<EOF
name			llvm_clang
version			$VER-1
architecture		arm64
summary			"The clang C/C++ compiler and the lld linker"
description		"clang and lld from LLVM $VER, cross-compiled for Haiku
arm64. Built for the AArch64 target only, with the tools trimmed down to a
compiler and a linker. LLVM already carries a Haiku triple and a Haiku
toolchain driver; what it cannot do is build itself for a target it cannot
run on, so this was cross-built with the tablegen tools built for the host."
packager		"The RENKU project"
vendor			"The RENKU project"
licenses {
	"Apache v2 with LLVM Exceptions"
}
copyrights {
	"2003-2025 the LLVM Project contributors"
}
provides {
	llvm_clang = $VER
	cmd:clang = $VER
	cmd:clang++ = $VER
	cmd:ld.lld = $VER
}
requires {
	haiku
	lib:libz
}
urls {
	"https://llvm.org/"
}
EOF

OUT="${1:-$LB/llvm_clang-$VER-1-arm64.hpkg}"
rm -f "$OUT"
( cd "$ST/boot/system" && "$PKG" create -q "$OUT" )
echo "built $OUT ($(du -h "$OUT" | cut -f1))"
