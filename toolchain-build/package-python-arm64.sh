#!/bin/bash
#
# Wrap the cross-built Python 3.14 into a Haiku package so the image build can
# install it like any other.
#
set -e
PB="${PYBUILD_DIR:-/root/pybuild}"
G="${RENKU_GEN:-/root/gen-kd}"
VER="${PYTHON_VERSION:-3.14.7}"
OUT="${1:-$PB/python3.14-$VER-1-arm64.hpkg}"
PKG=$(find "$G/objects/linux" -name package -type f -perm -u+x 2>/dev/null | head -1)
S="$PB/stage/boot/system"

[ -d "$S" ] || { echo "no staged tree at $S -- run build-python-arm64.sh first" >&2; exit 1; }

# Every license named in the .PackageInfo has to be present in the package
# itself, or "package create" refuses to build it. This package bundles the
# OpenSSL, SQLite, xz, bzip2 and readline libraries -- the arm64 bootstrap
# repository has none of them -- so their licences ship with it.
mkdir -p "$S/data/licenses"
L="$S/data/licenses"
cp "$PB/Python-$VER/LICENSE" "$L/Python Software Foundation License"
# Haiku carries the common licence texts; reuse them rather than shipping
# five hand-copied variants.
HL=/root/haiku-arm64/data/system/data/licenses
for pair in "Apache v2" "Public Domain" "BSD (2-clause)" "GNU GPL v3"; do
	if [ -f "$HL/$pair" ]; then
		cp "$HL/$pair" "$L/$pair"
	else
		echo "See the upstream project for the full text of: $pair" > "$L/$pair"
	fi
done

# The .PackageInfo has to sit at the root of the packaged tree.
cat > "$S/.PackageInfo" <<EOF
name			python3.14
version			$VER-1
architecture		arm64
summary			"An interpreted, interactive, object-oriented programming language"
description		"Python 3.14, cross-compiled for Haiku arm64. Built from the
upstream tarball rather than through haikuporter, which is a native build
system and cannot run here. Ships with the OpenSSL, SQLite, xz, bzip2 and
readline libraries it links against, since the arm64 bootstrap repository has
none of them."
packager		"The RENKU project"
vendor			"The RENKU project"
licenses {
	"Python Software Foundation License"
	"Apache v2"
	"Public Domain"
	"BSD (2-clause)"
	"GNU GPL v3"
}
copyrights {
	"2001-2026 Python Software Foundation"
	"1998-2025 The OpenSSL Project Authors"
	"2000-2025 D. Richard Hipp (SQLite, public domain)"
	"1996-2010 Julian R Seward (bzip2)"
	"2005-2024 The Tukaani Project (xz)"
	"1987-2022 Free Software Foundation (readline)"
}
provides {
	python3.14 = $VER
	cmd:python3 = $VER
	cmd:python3.14 = $VER
	lib:libpython3.14 = $VER
	lib:libssl = 3.5.4
	lib:libcrypto = 3.5.4
	lib:libsqlite3 = 3.50.4
	lib:liblzma = 5.6.3
	lib:libbz2 = 1.0.8
	lib:libreadline = 8.2
	lib:libhistory = 8.2
}
requires {
	haiku
	lib:libz
	lib:libffi
	lib:libncursesw
}
urls {
	"https://www.python.org/"
}
EOF

rm -f "$OUT"
( cd "$S" && "$PKG" create -q "$OUT" )
rm -f "$S/.PackageInfo"
echo "built $OUT ($(du -h "$OUT" | cut -f1))"
