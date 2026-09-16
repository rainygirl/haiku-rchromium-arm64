# R Chromium -- arm64 (AArch64)

**English** | [日本語](README.ja.md) | [한국어](README.ko.md)

Chromium running natively on Haiku/AArch64 -- Apple Silicon and other arm64
machines -- with a BeAPI toolbar: back/forward/reload, an address field, and
bookmarks. Noto Sans CJK is bundled, so Korean, Japanese and Chinese pages
render without extra fonts. It runs on the RENKU arm64 image (Haiku arm64 with the TLSDESC
loader patch); stock Haiku arm64 images cannot load it.

![R Chromium rendering news.naver.com on the Haiku arm64 desktop](docs/images/screenshot-naver.png)

## Install with pkgman

R Chromium is published in the `pkgman.rainygirl.com` package repository.
Open Terminal on the device:

```sh
pkgman add-repo https://pkgman.rainygirl.com/arm64
pkgman add-repo https://pkgman.rainygirl.com/arm64-system
pkgman install rchromium
```

Then **reboot**. R Chromium needs two fixes in the kernel and the runtime
loader that the RenkuOS nightly arm64 image does not carry yet (the TLSDESC
loader patch and the `query-valid-pte` kernel patch). The `arm64-system`
repository publishes a `haiku` system package with both; `pkgman install
rchromium` pulls it in as a dependency, and it takes effect on the next boot.
Until then R Chromium exits with `Troubles relocating: Bad data` or panics the
kernel.

The package is about 150 MB; keep that much free on `/boot`. It installs into
`/boot/system/apps/RChromium/`, adds **R Chromium** to
**Deskbar -> Applications**, and adds an `rchromium` command. Remove it with
`pkgman uninstall rchromium`.

If `pkgman add-repo` fails with `Operation not supported`, the image was built
without TLS support in its network kit (the RenkuOS nightly minimum image is).
Set the clock first -- that image boots at 1970-01-01 -- and use the HTTP
address instead:

```sh
date -u 091612002026        # MMDDhhmmYYYY, the current UTC time
yes | pkgman add-repo http://pkgman.rainygirl.com/arm64
yes | pkgman add-repo http://pkgman.rainygirl.com/arm64-system
pkgman install rchromium
```

and reboot afterwards. The clock is lost again on every boot of that image;
set it before starting R Chromium or every HTTPS site fails with
`ERR_CERT_DATE_INVALID`.

`yes |` answers the "overwrite?" question pkgman asks when a failed HTTPS
attempt left a repository entry behind.

## Install with the installer script

Open Terminal on the device and paste this one line:

```sh
python3 -c "import urllib.request as u;exec(u.urlopen('https://raw.githubusercontent.com/rainygirl/haiku-rchromium-arm64/main/install.py').read())"
```

It downloads the latest release (about 140 MB), installs it into
`~/config/non-packaged/apps/RChromium/`, adds **R Chromium** to
**Deskbar -> Applications** and the Desktop, and adds an `rchromium` command.
You need about 400 MB free on `/boot`.

From a checkout of this repository, `./install.sh` does the same.

## Run

Double-click **R Chromium** on the Desktop, or pick it from
**Deskbar -> Applications**. From Terminal:

```sh
rchromium https://news.naver.com
```

- **Back / Forward / Reload** -- icon buttons on the left; Reload turns into Stop
  while a page is loading.
- **Address field** -- type a URL and press Enter; a bare `example.com` opens
  `https://example.com`.
- **Star** -- bookmarks the current page under a date group ("Today", ...).
- **Menu** -- opens a searchable bookmarks window; double-click an entry to
  open it.

## Uninstall

```sh
python3 -c "import urllib.request as u;exec(u.urlopen('https://raw.githubusercontent.com/rainygirl/haiku-rchromium-arm64/main/install.py').read())" --uninstall
```

or `./install.sh --uninstall` from a checkout.

## AI disclosure

This program was written with Claude.
