#!/bin/bash
# Cross-configure CPython 3.14 for Haiku arm64 using the Haiku cross toolchain
# and the sysroot assembled from the RENKU arm64 build output.
set -e
PB=/root/pybuild
SR=$PB/sysroot/boot/system/develop
CT=/root/gen-arm64/cross-tools-arm64/bin/aarch64-unknown-haiku

# The cross gcc is configured with --with-sysroot and already knows the whole
# Haiku header layout: every headers/os subdirectory, and gnu and bsd ahead of
# posix so their #include_next wrappers resolve. Pointing its sysroot at the
# one we assembled is all that is needed -- no -I, no -B, no -L. Passing those
# by hand instead breaks C++ (#include_next cannot see past a -I directory)
# and libtool drops them when it relinks.
ln -sfn "$PB/sysroot" /root/gen-arm64/cross-tools-arm64/sysroot

export CC="$CT-gcc"
export CXX="$CT-g++"
export AR="$CT-ar"
export RANLIB="$CT-ranlib"
export READELF="$CT-readelf"

# Haiku hides its BSD/GNU extensions -- memrchr, strchrnul, pthread_getattr_np
# -- behind _DEFAULT_SOURCE, and Python's _POSIX_C_SOURCE/_XOPEN_SOURCE turns
# it off, so they end up used but never declared.
export CPPFLAGS="-D_DEFAULT_SOURCE"
export CFLAGS="-O2 -fPIC -D_DEFAULT_SOURCE"

# configure consults pkg-config, and an unset PKG_CONFIG_LIBDIR lets it answer
# from the host Linux .pc files: that is how _curses ended up asking for
# -lncursesw -ltinfo and headers under ncursesw/, neither of which exists on
# Haiku. Pinning it to the sysroot means pkg-config can only see the arm64
# packages, and anything with no arm64 build comes back missing, which is the
# right answer.
export PKG_CONFIG_LIBDIR=$SR/lib/pkgconfig

export CONFIG_SITE=$PB/cross-config.site

rm -rf $PB/build-arm64
mkdir -p $PB/build-arm64
cd $PB/build-arm64
$PB/Python-3.14.7/configure \
  --host=aarch64-unknown-haiku \
  --build=x86_64-pc-linux-gnu \
  --with-build-python=$PB/host/bin/python3.14 \
  --prefix=/boot/system \
  --enable-shared \
  --without-ensurepip \
  --disable-test-modules
