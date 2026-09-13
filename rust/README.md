# aarch64-unknown-haiku for Rust

Rust ships Haiku targets for i686 and x86_64 and nothing else. Chromium needs
one for arm64 and cannot do without Rust at all -- `enable_rust=false` fails at
`//skia:bridge_rust_side`, a hard dependency of the browser -- so this target
has to exist before any Chromium work on Haiku arm64 can start.

`build-rust-arm64.sh` clones rustc, adds the target, and builds a std for it.
About 15 minutes and 6 GB.

## What it takes

Less than expected: **26 lines**.

* `aarch64_unknown_haiku.rs` -- the target spec. The AArch64 data layout and
  `+v8a` come from `aarch64-unknown-freebsd`; the OS half is
  `base::haiku::opts()`, already in tree and not architecture-specific.
  `position_independent_executables` is set for the same reason x86_64 Haiku
  sets it: Haiku executables are ET_DYN.
* one line in `compiler/rustc_target/src/spec/mod.rs` registering it.

std itself needed no change. Its Haiku support is in
`library/std/src/os/haiku/` and is not gated on architecture.

## Two things that stop the build

* **`curl` must be installed.** rustc's bootstrap downloads its stage0 with
  it and fails immediately without it.
* **`BOOTSTRAP_SKIP_TARGET_SANITY=1`.** The stage0 compiler is a released
  beta, so it does not know the target that is being added, and bootstrap's
  sanity check refuses the build. That check is there to catch typos in a
  custom target name; here the name is deliberately new. The error message
  names the variable itself.

`download-ci-llvm = true` is worth keeping: rustc here is only a means to
cross-compile std, and building LLVM would add roughly two hours and more disk
than this container has.

## Verified

Cross-compiled on Linux, run in QEMU on Haiku arm64:

```
=== basic std
arch: arm64
os: haiku
hello from rust on Haiku arm64
  rc=0
=== threads, backtrace, env
backtrace captured: 7 frames-ish
thread returned 42
temp dir: "/tmp"
  rc=0
```

`HashMap`, threads, `std::backtrace` and `std::env` all work, so std is whole
rather than merely linking.

With this in place, `gn gen` for `target_os="haiku" target_cpu="arm64"` gets
past Rust and stops in the same place the x64 configuration does -- Chromium's
own feature flags.

## A known gap

`libc-haiku-aarch64.rs` in this directory is **not applied**, and nothing so
far has needed it.

The `libc` crate's `unix/haiku/mod.rs` selects an architecture module and
leaves aarch64 as a TODO:

```rust
} else if #[cfg(target_arch = "aarch64")] {
    // TODO
    // mod aarch64;
    // pub use self::aarch64::*;
}
```

so `mcontext_t` and `ucontext_t` are simply absent on this target. std builds
and runs without them, including backtraces. The file here translates Haiku's
`struct vregs` (`headers/posix/arch/arm64/signal.h`) into the shape the
x86_64 module uses, ready for whenever something does reach for those types --
signal handling that inspects registers is the likely first caller. It has
been written but not compiled, so treat it as a starting point rather than a
tested one.

## Upstreaming

The two rustc changes are `rustc-aarch64-haiku.diff` and are the shape a
`rust-lang/rust` pull request would take: a Tier 3 target addition, which
needs a target maintainer and a `platform-support` doc entry. The libc module,
if it turns out to be needed, belongs in `rust-lang/libc` instead.
