# R Chromium -- arm64 (AArch64)

Full Chromium `//chrome` built for Haiku on AArch64, so it runs on Apple
Silicon under Hypervisor.framework at native speed rather than emulating x86.

This is the sister port to `../rchromium-native-x86/`. The current binary is the
full `//chrome` (Chrome's own UI), but the direction (decided 2026-09-13) is to
converge on the same product as x86: `content_shell` wrapped in a hand-written
BeAPI toolbar, built here first and then ported to x86. See
[`docs/browser-ui-plan.md`](docs/browser-ui-plan.md) and [`AGENTS.md`](AGENTS.md).

## What is here

```
port/              the port generator: apply-haiku-port.sh + port-*.py + files/
rust/              the aarch64-unknown-haiku Rust toolchain patch and installer
toolchain-build/   cross-build of the sysroot, Python 3.14, gn/ninja, clang/lld
haiku_shim/        libchromium_haiku source: BeAPI subclasses compiled with the
                   system gcc, kept out of Chromium's clang objects (RTTI reasons)
packaging/         the hpkg PackageInfo
```

The Chromium checkout itself is not vendored here (tens of GB). `port/` is the
scaffolding applied on top of a fetched `chromium/src`.

## Building

Inside the `haiku-builder` container (Linux, cross-compiling to Haiku arm64):

```sh
# 1. Toolchain and build-time packages (sysroot, python, gn/ninja, clang/lld).
#    Hours; each step is skipped if its output already exists.
toolchain-build/build-all-arm64.sh

# 2. Rust with an aarch64-unknown-haiku target (Chromium's Rust cannot be
#    switched off, and stock rustc has no Haiku arm64 target).
rust/build-rust-arm64.sh
rust/install-rust-toolchain.sh <chromium-src>

# 3. Apply the Haiku port to a fetched Chromium checkout.
port/apply-haiku-port.sh <chromium-src>
python3 port/port-ozone.py <chromium-src>   # registers the Ozone platform + copies ui/ozone/platform/haiku

# 4. Configure and build.
cd <chromium-src>
gn gen out/haiku-arm64 --args='
    target_os="haiku" target_cpu="arm64" is_debug=false symbol_level=0
    haiku_sysroot="/root/pybuild/sysroot"
    haiku_gcc_lib_dir="<print-file-name of crtbeginS.o dir>"'
ninja -C out/haiku-arm64 chrome
```

The BeAPI shim library is built separately from `haiku_shim/` with the same gcc
that built `libbe` (not Chromium's clang) and linked as `libchromium_haiku`;
`haiku_shim/haiku_shim.h` explains why.

## Installing and running on the device

Verified on the real renku-arm64 Haiku desktop (booted on Apple Silicon under
QEMU/HVF); the same steps apply to Haiku arm64 on hardware.

### Prerequisites (the image)

- **`A0001` runtime_loader TLSDESC patch.** clang emits `R_AARCH64_TLSDESC`
  relocations that a stock Haiku loader cannot resolve, so `content_shell` (and
  `libtest_trace_processor.so`) will not load. The image's loader must carry
  `../haiku_kernel_patches/A0001-arm64-runtime-loader-tlsdesc.patch`. If your
  image predates it, graft a rebuilt `runtime_loader` into the image's
  `haiku.hpkg` (`jam runtime_loader`, then `package add -f <hpkg> runtime_loader`
  at the package top level, written back with `bfs_shell`, `sync` before `quit`)
  -- the full recipe is in [`AGENTS.md`](AGENTS.md).
- **Standard Haiku fonts.** Text is shaped and rasterised through the fontations
  backend against the system fonts; the stock RENKU/Haiku font set is enough
  (Korean on news.naver.com renders with it).

### Deploy

Put the binary, its resources, and the BeAPI shim together, e.g. under a `cs/`
directory on any writable BFS volume:

```
cs/content_shell                 # the binary
cs/content_shell.pak             # resources ...
cs/icudtl.dat
cs/snapshot_blob.bin
cs/v8_context_snapshot.bin
cs/locales/
cs/lib/libchromium_haiku.so      # the BeAPI shim (see below)
```

`content_shell` has a `DT_NEEDED` on `libchromium_haiku` (the native toolbar
shim), so point the loader at `cs/lib` when launching:

```sh
cd cs
LIBRARY_PATH=$(pwd)/lib:/boot/system/lib ./content_shell https://news.naver.com
```

The shim must be relinked with 4 KB pages, or the loader rejects it
(`libchromium_haiku.so: Troubles handling dynamic section`) -- gcc defaults to a
64 KB `max-page-size` on arm64, whose offset<->vaddr skew the loader mis-maps:

```sh
aarch64-unknown-haiku-g++ -shared haiku_shim.o -o libchromium_haiku.so \
    -Wl,-soname,libchromium_haiku.so -Wl,--hash-style=both \
    -Wl,-z,max-page-size=0x1000 -lbe -lstdc++ -lroot
```

### Run

No launch flags are needed any more -- the port appends `--in-process-gpu` and
`--disable-gpu` itself on Haiku (Haiku has no GL, so the page composites in
software and the display compositor runs in the browser process, next to the
BWindow). Just:

```sh
./content_shell https://news.naver.com
```

A native BeAPI window opens with the hand-written toolbar (address bar,
back/forward/reload, bookmarks) drawn by the ozone layer.

### Verified behaviour and limits

- news.naver.com renders fully (Korean text, broadcaster logos, LIVE video
  thumbnails) with zero crashes; simple pages likewise. Native toolbar,
  address-bar navigation, and bookmarks work.
- The earlier "naver is a use-after-free / blob corruption" diagnosis was wrong;
  the real cause was the missing software-compositing wiring fixed above. See
  [`AGENTS.md`](AGENTS.md) for the full root-cause writeup and the remaining
  rough edges.

## Relationship to the x86 port

`../rchromium-native-x86/` has its own, independently written native toolbar
(Chromium 87, BControlLook-drawn) that meets the same user spec. It is not a
backport of this one and this is not a backport of it -- the Chromium 87 vs 154
APIs differ, so no source is shared. What IS shared is the design: a widget-keyed
bridge so content_shell never sees a BeAPI type, RTTI isolation in a separately
built shim, an explicit `platform_->aura->ShowWindow()` in the delegate, and the
SetAddressBarURL / SetIsLoading / EnableUIControl hook mapping. Both toolbars
already exist and work; do not reimplement one to match the other unless the user
asks to converge the two styles. See `AGENTS.md` for detail.

## 요약

AArch64용 전체 Chromium 154 포트입니다. `../x86/`(32비트 content_shell)와는 다른
포트로, 크로스 툴체인(clang/lld, Rust, Python, gn/ninja)부터 새로 빌드해
`//chrome`를 만듭니다. 빌드는 M4의 `haiku-builder` 컨테이너에서, 실행은 실기
renku-arm64 Haiku 데스크톱(Apple Silicon + QEMU/HVF, 또는 arm64 하드웨어)에서
합니다. 이미지에는 `A0001` TLSDESC 로더 패치가 필요합니다. 설치/실행 절차는 위의
"Installing and running on the device"를 참고하세요.
