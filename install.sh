#!/bin/sh
#
# Installs R Chromium (arm64) on Haiku from the prebuilt release tarball.
# Thin wrapper around install.py; run on Haiku itself.
#
# Usage:
#   ./install.sh                 download the latest release and install
#   ./install.sh --uninstall     remove it again
#   ./install.sh --file X.tar.gz install from a local tarball
#   ./install.sh --prefix DIR    install somewhere other than
#                                ~/config/non-packaged/apps/RChromium
exec python3 "$(dirname "$0")/install.py" "$@"
