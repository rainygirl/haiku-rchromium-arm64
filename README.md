# R Chromium -- arm64 (AArch64)

**English** | [日本語](README.ja.md) | [한국어](README.ko.md)

Chromium running natively on Haiku/AArch64 -- Apple Silicon and other arm64
machines -- with a BeAPI toolbar: back/forward/reload, an address field, and
bookmarks. Noto Sans CJK is bundled, so Korean, Japanese and Chinese pages
render without extra fonts. It runs on the RENKU arm64 image (Haiku arm64 with the TLSDESC
loader patch); stock Haiku arm64 images cannot load it.

![R Chromium rendering news.naver.com on the Haiku arm64 desktop](docs/images/screenshot-naver.png)

## Install

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
