# R Chromium -- arm64 (AArch64)

**English** | [日本語](README.ja.md) | [한국어](README.ko.md)

A native Haiku/AArch64 build of Chromium's `content_shell` wrapped in a
hand-written BeAPI toolbar, so it runs on Apple Silicon (and arm64 hardware) at
native speed rather than emulating x86. This is the end-user install and run
guide.

Build, architecture, and porting internals are in [`AGENTS.md`](AGENTS.md).

![R Chromium rendering news.naver.com on the Haiku arm64 desktop](docs/images/screenshot-naver.png)

*news.naver.com rendered on the RENKU (Haiku arm64) desktop with the native
BeAPI toolbar. Captured from the QEMU/HVF VM on an Apple Silicon Mac.*

## Requirements

- **Haiku on AArch64** -- the real renku-arm64 desktop (booted on Apple Silicon
  under QEMU/HVF, or arm64 hardware).
- **`A0001` runtime_loader TLSDESC patch in the image.** clang emits
  `R_AARCH64_TLSDESC` relocations that a stock Haiku loader cannot resolve, so
  the binary will not load without it. The patch is
  `haiku_kernel_patches/A0001-arm64-runtime-loader-tlsdesc.patch`; grafting it
  into an existing image's `haiku.hpkg` is described in [`AGENTS.md`](AGENTS.md).
- **The standard Haiku fonts.** Text is shaped and rasterised against the system
  fonts; the stock RENKU/Haiku font set is enough (Korean on news.naver.com
  renders with it).

## Installing and running on the device

### Deploy

Put the binary, its resources, and the BeAPI shim (`libchromium_haiku.so`)
together, e.g. under a `cs/` directory on any writable BFS volume:

```
cs/content_shell                 # the binary
cs/content_shell.pak             # resources ...
cs/icudtl.dat
cs/snapshot_blob.bin
cs/v8_context_snapshot.bin
cs/locales/
cs/lib/libchromium_haiku.so      # the native BeAPI toolbar shim
```

### Run

`content_shell` needs the shim (`DT_NEEDED: libchromium_haiku`), so point the
loader at `cs/lib`. No launch flags are needed -- the build enables software
compositing on Haiku by itself:

```sh
cd cs
LIBRARY_PATH=$(pwd)/lib:/boot/system/lib ./content_shell https://news.naver.com
```

A native Haiku window opens with the toolbar and the page rendered below it.

### Using the browser

The toolbar across the top of the window is drawn with BeAPI controls:

- **Back / Forward / Reload** -- icon buttons on the left; Reload turns into Stop
  while a page is loading.
- **Address field** -- type a URL and press Enter to navigate; a bare
  `example.com` is treated as `https://example.com`. The field tracks the
  current page's URL.
- **Add bookmark (star)** -- files the current page into the bookmarks store
  under a date group ("Today", ...).
- **Show bookmarks** -- opens a searchable bookmarks window; double-click an
  entry to open it.

### Known limits and troubleshooting

- **`libchromium_haiku.so: Troubles handling dynamic section` at launch** -- the
  shim was not linked with 4 KB pages. Use the shim from a correct build (the
  relink flag and reason are in [`AGENTS.md`](AGENTS.md)).
- **`Bad data relocating` / the binary refuses to load** -- the image's loader
  lacks the `A0001` TLSDESC patch (see Requirements).
- news.naver.com and other pages render fully with the native toolbar,
  address-bar navigation, and bookmarks. The full verification history and the
  known rough edges are in [`AGENTS.md`](AGENTS.md).
