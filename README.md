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

## Running

The RENKU arm64 image must carry the `A0001` runtime_loader TLSDESC patch (see
`../haiku_kernel_patches/`), or the binary will not load. Launch flags that the
port currently needs are recorded in `AGENTS.md`.

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
`//chrome`를 만듭니다. 빌드는 M4의 `haiku-builder` 컨테이너에서, 실행은 RENKU
arm64 QEMU 이미지에서 합니다. 이미지에는 `A0001` TLSDESC 커널 패치가 필요합니다.
