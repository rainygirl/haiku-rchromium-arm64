#!/bin/bash
#
# Cross-build the libraries CPython's optional modules need, for Haiku arm64,
# and install them into the sysroot.
#
# The arm64 package repository in the Haiku tree is a 35-package bootstrap set:
# zlib, libffi, ncurses, expat and icu, and nothing else. Without these,
# python3.14 comes out missing ssl, hashlib, sqlite3, lzma, bz2 and readline.
# haikuporter cannot help -- it is a native build system that runs inside
# Haiku -- so each of these is cross-compiled here.
#
set -u

PB="${PYBUILD_DIR:-/root/pybuild}"
SRC="$PB/deps"
ROOT="${SYSROOT:-$PB/sysroot}"
SR="$ROOT/boot/system/develop"
RT="$ROOT/boot/system/lib"
CT=/root/gen-arm64/cross-tools-arm64/bin/aarch64-unknown-haiku
HOST=aarch64-unknown-haiku
JOBS="${JOBS:-8}"

BZIP2_V=1.0.8
XZ_V=5.6.3
OPENSSL_V=3.5.4
SQLITE_Y=2025
SQLITE_V=3500400
READLINE_V=8.2

# The cross gcc is configured with --with-sysroot and already knows the whole
# Haiku header layout -- every headers/os subdirectory, and gnu and bsd ahead
# of posix so their #include_next wrappers resolve. Pointing its sysroot at
# the one we assembled is all that is needed: no -I, no -B, no -L. Passing
# those by hand instead breaks C++ (#include_next cannot see past a -I
# directory) and libtool drops them when it relinks, which is what the
# "cannot find crti.o" failures were.
ln -sfn "$ROOT" /root/gen-arm64/cross-tools-arm64/sysroot

export CC="$CT-gcc" CXX="$CT-g++" AR="$CT-ar" RANLIB="$CT-ranlib"
export STRIP="$CT-strip" LD="$CT-ld"
export CPPFLAGS="-D_DEFAULT_SOURCE"
export CFLAGS="-O2 -fPIC -D_DEFAULT_SOURCE"
export LDFLAGS=""
export PKG_CONFIG_LIBDIR="$SR/lib/pkgconfig"

mkdir -p "$SRC" "$RT" "$SR/lib/pkgconfig"

log()  { printf '\n=== %s\n' "$*"; }
fail() { printf '    FAILED: %s\n' "$*"; }

get() {
	local f=${1##*/}
	[ -f "$SRC/$f" ] || wget -q "$1" -O "$SRC/$f" || return 1
	case $f in
		*.tar.gz|*.tgz) tar xzf "$SRC/$f" -C "$SRC" ;;
		*.tar.xz)       tar xJf "$SRC/$f" -C "$SRC" ;;
		*.tar.bz2)      tar xjf "$SRC/$f" -C "$SRC" ;;
	esac
}

# Fold one DESTDIR tree into the sysroot. Called right after each library so a
# failure late in the list does not discard what already built.
install_tree() {
	local d="$1"
	[ -d "$d" ] || return 0
	local b="$d/boot/system"
	[ -d "$b/develop/headers" ] && cp -a "$b/develop/headers"/. "$SR/headers/" 2>/dev/null
	[ -d "$b/develop/lib" ]     && cp -a "$b/develop/lib"/.     "$SR/lib/"     2>/dev/null
	[ -d "$b/lib" ]             && cp -a "$b/lib"/.             "$RT/"         2>/dev/null
	# Several of these use a plain autotools layout rather than Haiku's
	# develop/ split.
	[ -d "$b/include" ] && cp -a "$b/include"/. "$SR/headers/" 2>/dev/null

	# --prefix=/boot/system puts the libraries in boot/system/lib, but
	# develop/lib is the only directory the linker is given, so every
	# link-time name has to be reachable from there too.
	local f n
	for f in "$RT"/*.so "$RT"/*.so.*; do
		[ -e "$f" ] || continue
		n=$(basename "$f")
		[ -e "$SR/lib/$n" ] || ln -sf "../../lib/$n" "$SR/lib/$n"
	done
	for f in "$b"/lib/pkgconfig "$b"/develop/lib/pkgconfig; do
		[ -d "$f" ] && cp -a "$f"/. "$SR/lib/pkgconfig/" 2>/dev/null
	done
	return 0
}

# --- bzip2 --------------------------------------------------------------
# No configure script, and its Makefile hardcodes gcc and only builds a static
# library, so drive it by hand and link the shared object ourselves.
if [ ! -e "$SR/lib/libbz2.so" ]; then
	log "bzip2 $BZIP2_V"
	if get "https://sourceware.org/pub/bzip2/bzip2-$BZIP2_V.tar.gz" &&
	   cd "$SRC/bzip2-$BZIP2_V"; then
		make clean >/dev/null 2>&1
		if make -j"$JOBS" CC="$CC" AR="$AR" RANLIB="$RANLIB" \
		        CFLAGS="$CFLAGS -D_FILE_OFFSET_BITS=64" libbz2.a &&
		   $CC -shared -Wl,-soname,libbz2.so.1.0 -o libbz2.so.1.0.8 \
		        blocksort.o huffman.o crctable.o randtable.o compress.o \
		        decompress.o bzlib.o; then
			cp libbz2.so.1.0.8 "$RT/"
			ln -sf libbz2.so.1.0.8 "$RT/libbz2.so.1.0"
			ln -sf libbz2.so.1.0.8 "$RT/libbz2.so.1"
			ln -sf ../../lib/libbz2.so.1.0.8 "$SR/lib/libbz2.so"
			cp libbz2.a "$SR/lib/"
			cp bzlib.h "$SR/headers/"
		else fail bzip2; fi
	else fail "bzip2 (fetch)"; fi
fi

# --- xz (liblzma) -------------------------------------------------------
if [ ! -e "$SR/lib/liblzma.so" ]; then
	log "xz $XZ_V"
	rm -rf "$SRC/xz-$XZ_V" "$SRC/inst-xz"
	if get "https://github.com/tukaani-project/xz/releases/download/v$XZ_V/xz-$XZ_V.tar.gz" &&
	   cd "$SRC/xz-$XZ_V" &&
	   ./configure --host=$HOST --prefix=/boot/system --disable-static \
	       --enable-shared --disable-xz --disable-xzdec --disable-lzmadec \
	       --disable-lzmainfo --disable-scripts --disable-doc >/dev/null &&
	   make -j"$JOBS" >/dev/null && make install DESTDIR="$SRC/inst-xz" >/dev/null
	then install_tree "$SRC/inst-xz"; else fail xz; fi
fi

# --- openssl ------------------------------------------------------------
if [ ! -e "$SR/lib/libssl.so" ]; then
	log "openssl $OPENSSL_V"
	rm -rf "$SRC/openssl-$OPENSSL_V" "$SRC/inst-ssl"
	if get "https://github.com/openssl/openssl/releases/download/openssl-$OPENSSL_V/openssl-$OPENSSL_V.tar.gz" &&
	   cd "$SRC/openssl-$OPENSSL_V"
	then
		# OpenSSL ships no Haiku arm64 target; haiku-x86_64 is the closest
		# one it has. --cross-compile-prefix is prepended to $CC, so CC has
		# to be the bare name or the prefix ends up doubled and every
		# compile is "command not found".
		if CC=gcc CXX=g++ AR=ar RANLIB=ranlib LD=ld \
		   ./Configure haiku-x86_64 no-asm no-tests no-docs shared \
		       --prefix=/boot/system \
		       --openssldir=/boot/system/settings/ssl \
		       --cross-compile-prefix="$CT-" >/dev/null
		then
			# That target hardcodes the x86_64 word size.
			sed -i 's/-m64//g' Makefile
			if make -j"$JOBS" build_libs >/dev/null 2>&1 &&
			   make install_dev DESTDIR="$SRC/inst-ssl" >/dev/null 2>&1 &&
			   make install_runtime_libs DESTDIR="$SRC/inst-ssl" >/dev/null 2>&1
			then install_tree "$SRC/inst-ssl"; else fail "openssl (build)"; fi
		else fail "openssl (Configure)"; fi
	else fail "openssl (fetch)"; fi
fi

# --- sqlite -------------------------------------------------------------
if [ ! -e "$SR/lib/libsqlite3.so" ]; then
	log "sqlite $SQLITE_V"
	rm -rf "$SRC/sqlite-autoconf-$SQLITE_V" "$SRC/inst-sqlite"
	if get "https://www.sqlite.org/$SQLITE_Y/sqlite-autoconf-$SQLITE_V.tar.gz" &&
	   cd "$SRC/sqlite-autoconf-$SQLITE_V" &&
	   ./configure --host=$HOST --prefix=/boot/system --disable-static \
	       --enable-shared --disable-readline >/dev/null &&
	   make -j"$JOBS" >/dev/null && make install DESTDIR="$SRC/inst-sqlite" >/dev/null
	then install_tree "$SRC/inst-sqlite"; else fail sqlite; fi
fi

# --- readline -----------------------------------------------------------
if [ ! -e "$SR/lib/libreadline.so" ]; then
	log "readline $READLINE_V"
	rm -rf "$SRC/readline-$READLINE_V" "$SRC/inst-readline"
	if get "https://ftp.gnu.org/gnu/readline/readline-$READLINE_V.tar.gz" &&
	   cd "$SRC/readline-$READLINE_V" &&
	   # readline probes the terminal at configure time and cannot when
	   # cross-building, so it has to be told the answer.
	   bash_cv_wcwidth_broken=no ./configure --host=$HOST \
	       --prefix=/boot/system --disable-static --enable-shared \
	       --with-curses >/dev/null &&
	   # SHLIB_LIBS has to be repeated on install: the shlib sub-make
	   # re-evaluates its link rules there and fails without it.
	   make -j"$JOBS" SHLIB_LIBS="-lncursesw" >/dev/null &&
	   make install DESTDIR="$SRC/inst-readline" SHLIB_LIBS="-lncursesw" >/dev/null
	then
		install_tree "$SRC/inst-readline"
		# readline installs libreadline.so.8 but no bare .so, which is the
		# name -lreadline looks for.
		[ -e "$SR/lib/libreadline.so" ] || ln -sf ../../lib/libreadline.so.8 "$SR/lib/libreadline.so"
		[ -e "$SR/lib/libhistory.so" ]  || ln -sf ../../lib/libhistory.so.8  "$SR/lib/libhistory.so"
	else fail readline; fi
fi

echo
echo "libraries in the sysroot:"
for n in libz libffi libncursesw libbz2 liblzma libssl libcrypto libsqlite3 libreadline; do
	if [ -e "$SR/lib/$n.so" ]; then echo "  yes  $n"; else echo "  NO   $n"; fi
done
