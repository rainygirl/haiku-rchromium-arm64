#!/bin/bash
#
# Cross-build CPython 3.14.7 for Haiku arm64.
#
# This is step 1 of the Chromium arm64 port: Chromium's build needs a working
# Python 3 for the host of its own generators, and arm64 Haiku has no python
# beyond the 3.10 bootstrap package. haikuporter is not usable here -- it is a
# native build system that runs inside Haiku -- so this cross-builds from the
# upstream tarball with the Haiku cross toolchain.
#
# Runs inside the haiku-builder container.
#
set -e

PB="${PYBUILD_DIR:-/root/pybuild}"
G="${RENKU_GEN:-/root/gen-kd}"
VER="${PYTHON_VERSION:-3.14.7}"
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
JOBS="${JOBS:-8}"

log() { printf '\n=== %s\n' "$*"; }

mkdir -p "$PB"
cd "$PB"

# ---------------------------------------------------------------------------
log "Fetching CPython $VER"
# ---------------------------------------------------------------------------
if [ ! -d "Python-$VER" ]; then
	[ -f "Python-$VER.tar.xz" ] || \
		curl -fLO "https://www.python.org/ftp/python/$VER/Python-$VER.tar.xz"
	tar xf "Python-$VER.tar.xz"
fi

# ---------------------------------------------------------------------------
log "Teaching configure about Haiku cross builds"
# ---------------------------------------------------------------------------
# configure.ac has two lists of cross-build targets. The first (MACHDEP) knows
# about Haiku; the second (_PYTHON_HOST_PLATFORM) does not, and without an
# entry there configure stops with "cross build not supported for
# aarch64-unknown-haiku".
cd "Python-$VER"
if ! grep -q '\*-\*-haiku\*)' configure.ac || \
   [ "$(grep -c '\*-\*-haiku\*)' configure.ac)" -lt 2 ]; then
	python3 - <<'PY'
p = "configure.ac"
s = open(p).read()
old = """	*-*-vxworks*)
		_host_ident=$host_cpu
		;;"""
new = """	*-*-haiku*)
		_host_ident=$host_cpu
		;;
	*-*-vxworks*)
		_host_ident=$host_cpu
		;;"""
if s.count(old) == 1:
    open(p, "w").write(s.replace(old, new))
    print("  configure.ac: added the Haiku host case")
else:
    raise SystemExit("configure.ac does not look like %s" % p)
PY
	# autoconf 2.72 is what CPython 3.14 expects; the distro's may be older.
	if [ -x /root/autoconf-2.72/bin/autoconf ]; then
		PATH=/root/autoconf-2.72/bin:$PATH autoconf -o configure
	else
		autoconf -o configure
	fi
	chmod +x configure
fi
cd "$PB"

# ---------------------------------------------------------------------------
log "Building the host interpreter"
# ---------------------------------------------------------------------------
# Cross-building CPython needs a same-version interpreter on the host to run
# the freeze and deepfreeze generators.
if [ ! -x "$PB/host/bin/python3.14" ]; then
	rm -rf "$PB/build-host"
	mkdir -p "$PB/build-host"
	cd "$PB/build-host"
	"$PB/Python-$VER/configure" --prefix="$PB/host" --without-ensurepip
	make -j"$JOBS"
	make install
	cd "$PB"
fi

# ---------------------------------------------------------------------------
log "Assembling the cross sysroot"
# ---------------------------------------------------------------------------
SYSROOT="$PB/sysroot" RENKU_GEN="$G" "$HERE/make-sysroot.sh"

# ---------------------------------------------------------------------------
log "Cross-configuring and building"
# ---------------------------------------------------------------------------
cp "$HERE/cross-config.site" "$PB/cross-config.site"
"$HERE/cross-configure.sh"
cd "$PB/build-arm64"
make -j"$JOBS"

# ---------------------------------------------------------------------------
log "Staging"
# ---------------------------------------------------------------------------
rm -rf "$PB/stage"
make DESTDIR="$PB/stage" install

# Unstripped this is 165 MB, nearly all of it debug info in libpython and the
# static library. The ISO does not have room to spare.
STRIP=/root/gen-arm64/cross-tools-arm64/bin/aarch64-unknown-haiku-strip
find "$PB/stage" -type f \( -name '*.so' -o -name '*.so.*' \
	-o -name 'python3.14' -o -name '*.a' \) \
	-exec "$STRIP" --strip-unneeded {} \; 2>/dev/null || true

echo
echo "Staged at $PB/stage ($(du -sh "$PB/stage" | cut -f1))"
file "$PB/stage/boot/system/bin/python3.14"
