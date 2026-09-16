#!/bin/sh
#
# Installs R Chromium (arm64) on Haiku with pkgman. Run on the device itself.
#
#   sh install.sh                install (or update) R Chromium
#   sh install.sh --uninstall    remove it again
#   sh install.sh --tarball ...  old path: unpack the release tarball with
#                                install.py (needs python3; see --help there)
#   sh install.sh --url BASE     use another repository host
#
# R Chromium needs two fixes in the kernel and the runtime loader that the
# RenkuOS nightly arm64 image does not carry. The "arm64-system" repository
# publishes a "haiku" system package with both; installing rchromium pulls it
# in, and it takes effect after a reboot.
#
# Only tools present on the minimum image are used: no sed, grep, curl, wget
# or python3. openssl is the one network client every image has.
set -e

BASE="${RCHROMIUM_REPO_BASE:-https://pkgman.rainygirl.com}"
MODE=install

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
	case "$1" in
		--uninstall) MODE=uninstall; shift ;;
		--tarball) shift; exec python3 "$(dirname "$0")/install.py" "$@" ;;
		--url) BASE="${2%/}"; shift 2 ;;
		--url=*) BASE="${1#--url=}"; BASE="${BASE%/}"; shift ;;
		-h|--help)
			cat <<'EOF'
Installs R Chromium (arm64) on Haiku with pkgman.

  sh install.sh                install (or update) R Chromium
  sh install.sh --uninstall    remove it again
  sh install.sh --tarball ...  unpack the release tarball with install.py instead
  sh install.sh --url BASE     use another repository host

Reboot after the first install: it replaces the "haiku" system package with
one that has the kernel and runtime loader fixes R Chromium needs.
EOF
			exit 0 ;;
		*) die "unknown option: $1 (try --help)" ;;
	esac
done

command -v pkgman >/dev/null 2>&1 || die "pkgman not found - run this on Haiku."

if [ "$MODE" = uninstall ]; then
	info "removing rchromium"
	pkgman uninstall -y rchromium < /dev/null
	info "removed. The patched haiku system package stays; it is harmless."
	exit 0
fi

# --- clock ------------------------------------------------------------------
# The QEMU arm64 images boot at 1970-01-01. Every HTTPS certificate is "not yet
# valid" then and R Chromium itself shows ERR_CERT_DATE_INVALID on every site,
# so take the time from the server's Date header. -quiet keeps openssl going
# despite the failed certificate check.
http_head_date() {
	rest="${1#https://}"; host="${rest%%/*}"
	printf 'GET / HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n\r\n' "$host" \
		| openssl s_client -quiet -connect "$host:443" -servername "$host" 2>/dev/null \
		| tr -d '\r' | while IFS= read -r line; do
			case "$line" in
				[Dd]ate:*) printf '%s\n' "${line#*: }"; break ;;
				"") break ;;
			esac
		done
}

# "Wed, 16 Sep 2026 09:10:42 GMT" -> date -u 091609102026.42
set_clock() {
	[ $# -ge 5 ] || return 1
	case "$3" in
		Jan) m=01 ;; Feb) m=02 ;; Mar) m=03 ;; Apr) m=04 ;; May) m=05 ;; Jun) m=06 ;;
		Jul) m=07 ;; Aug) m=08 ;; Sep) m=09 ;; Oct) m=10 ;; Nov) m=11 ;; Dec) m=12 ;;
		*) return 1 ;;
	esac
	d="$2"; [ ${#d} -eq 1 ] && d="0$d"
	hh="${5%%:*}"; rest="${5#*:}"; mi="${rest%%:*}"; ss="${rest#*:}"
	date -u "$m$d$hh$mi$4.$ss" >/dev/null
}

if [ "$(date -u +%Y)" -lt 2020 ]; then
	warn "system clock says $(date -u +%Y); setting it from $BASE"
	# shellcheck disable=SC2046
	if set_clock $(http_head_date "$BASE"); then
		info "clock set to $(date -u)"
	else
		warn "could not set the clock; do it by hand: date -u MMDDhhmmYYYY"
	fi
fi

# --- repositories -----------------------------------------------------------
# pkgman asks "overwrite?" when a repository entry with that name exists (a
# failed HTTPS attempt leaves one behind) and re-asks forever on EOF, so it is
# fed "yes". Images whose network kit was built without TLS fail every HTTPS
# repository with "Operation not supported"; both repositories are served over
# plain HTTP too, and packages are checksummed against the index.
add_repo() {
	yes | pkgman add-repo "$1" && return 0
	case "$1" in
		https://*)
			warn "HTTPS failed; retrying over HTTP"
			yes | pkgman add-repo "http://${1#https://}" ;;
		*) return 1 ;;
	esac
}

info "registering $BASE/arm64"
add_repo "$BASE/arm64" || die "could not add $BASE/arm64"
info "registering $BASE/arm64-system"
add_repo "$BASE/arm64-system" || die "could not add $BASE/arm64-system"
pkgman refresh < /dev/null || warn "pkgman refresh reported an error; continuing"

# --- install ----------------------------------------------------------------
haiku_before="$(ls /system/packages/haiku-*.hpkg 2>/dev/null)"

info "installing rchromium"
pkgman install -y rchromium < /dev/null

haiku_after="$(ls /system/packages/haiku-*.hpkg 2>/dev/null)"
info "installed. Find R Chromium in Deskbar -> Applications, or run: rchromium <URL>"
if [ "$haiku_before" != "$haiku_after" ]; then
	warn "the haiku system package was replaced with one carrying the kernel and"
	warn "runtime loader fixes. REBOOT now; R Chromium does not run on the old kernel."
	warn "after the reboot, set the clock again before starting it."
fi
