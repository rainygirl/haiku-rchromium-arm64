# Chromium on Haiku -- port scaffolding

Step 4 of the arm64 work. This is where the port stands, and what stops it.

## Where it stands

**`//base` builds.** `obj/base/libbase.a`, 492 AArch64 objects, no failures.
2,206 object files in total for the Haiku target. `gn gen` covers 39,374
targets; the browser itself is far from built, but the foundation everything
else sits on is done.

`apply-haiku-port.sh <chromium-src>` applies the port and is safe to re-run.
The scripts are the source of truth; `haiku-port.diff` is a snapshot from the
gn-gen milestone and does not include the source fixes made since.

### What made this go fast

Fixing one error per build cycle cost 5-8 minutes each. `ninja -k 0` does not
stop at the first failure, so one pass collects every error in the target. The
first such pass turned up **259 errors** -- and 234 of them were the same
thing in one abseil header. Six fixes cleared 253 of the 259.

The errors are not spread evenly; they cluster hard, and finding the clusters
is worth far more than fixing individual sites. Always build with `-k 0`.

Two clusters dominated everything else.

**epoll.** Haiku has `poll()` but neither `epoll` nor `kqueue`, and Chromium
removed its libevent pump, so `message_pump_for_io.h` mapped every POSIX
platform to `MessagePumpEpoll` -- a header that reaches most of //base through
`base/task/current_thread.h`. One include was failing 18 of 20 targets.

Writing a poll-based pump would have been about a thousand lines. It was not
necessary: `MessagePumpEpoll` already carries a complete `poll()`
implementation behind the `kUsePollForMessagePumpEpoll` feature, added for
Android scheduler behaviour rather than portability. On that path
`epoll_event` is only a struct carrying results and the `EPOLL*` values only
bit flags, so `base/message_loop/epoll_shim_haiku.h` supplies the type and the
constants, the six epoll calls are compiled out, and the poll path is forced
on. The pump's logic -- interests, one-shot semantics, the wake event, the run
loop -- is untouched and still shared with every other platform.

**int_fast8_t.** Haiku defines it as `int`, which the standard allows; glibc
makes it `signed char`. abseil's cctz declares its civil-time fields as
`int_least8_t` and its arguments as `int_fast8_t`, so on Haiku every field
initialiser narrows and `-Wimplicit-int-conversion` turns each into an error.
Suppressed for cctz alone through Chromium's `warning_suppression.txt`, which
exists for exactly this -- suppressing by originating file rather than by
`-Wno` across a whole compilation.

### What //base needed

Beyond those two, about thirty small things, all of one kind: Haiku is POSIX
but not Linux.

| what Haiku lacks | what it got instead |
|---|---|
| `sys/syscall.h` | the include guarded; every `syscall()` was already inside a Linux guard |
| `linux/futex.h`, Linux `mcontext_t` | the sampling profiler's POSIX backend left out |
| `epoll` | the pump's own poll path |
| `mincore` | residency unmeasurable; the existing failure path |
| `RLIMIT_NICE`, `NZERO` | `CanLowerNiceTo` returns false |
| `SO_PASSCRED`, `SCM_CREDENTIALS` | handled as macOS already is |
| `/proc/meminfo` | `get_system_info()`, in `process_metrics_haiku.cc` |
| `/proc/self/fd` | `/dev/fd`, as on Solaris |
| `/sys/dev/block` | drive characteristics reported unknown |
| `setproctitle` | compiled out |
| `CLOCK_MONOTONIC_COARSE` | the plain monotonic clock |
| `PF_X` | defined from the ELF specification |
| integer `pthread_t` | `find_thread(nullptr)` -- Haiku's own thread id |

### The next wall: crubit

`net` and `mojo` reach 2,198 of 3,758 targets and then stop at crubit's
`cc_bindings_from_rs`, which generates C++ bindings for Rust APIs.

The tool links the bundled rustc's internals, so it knows only the targets
that rustc was built with -- and this port replaces rustc with one that has a
target the bundle does not. Two things were tried:

* **Turning it off.** `enable_cpp_api_from_rust` exists for this, but the
  consumers do not check it: `//components/cbor`, `//components/qr_code_generator`
  and `//third_party/blink/renderer/platform` depend on
  `//build/rust/crubit` under `!is_cronet_build` alone, so gn then fails with
  unresolved dependencies. Reverted.
* **A JSON target spec.** `cc_bindings_from_rs --target` takes a path as well
  as a triple, and
  `rustc -Zunstable-options --print target-spec-json` writes one. That gets
  past "could not find specification" -- and straight into
  `found crate std compiled by an incompatible version of rustc`, which is
  the real problem: the tool is built against the bundled rustc's std, not
  the replacement's.

So the honest fix is to rebuild crubit against the rustc this port uses. That
is what the bundle does for itself; doing it here means building
`cc_bindings_from_rs` from the crubit source with the replacement toolchain.
Not attempted yet.

### The Rust toolchain needed two more fixes

Chromium's generated `build/rust/std/rules/BUILD.gn` describes the rustc it
bundles, file by file. A rustc built from a different revision disagrees with
it in both directions, and `sync-std-sources.py` reconciles both -- removing
names whose files are gone, adding files the list does not name. Two things
that took several tries to get right: `inputs` blocks hold `.rs` as well as
`.md` (compiler-builtins reaches its sibling libm that way), and gnrt writes
some paths with `../..` in them, so they have to be normalised before
comparing.

It also gives `panic_abort` its dependency on `alloc`. Chromium's rules add
that only under `is_android`, matching the bundled rustc; the revision built
here uses `alloc::boxed::Box` unconditionally.

### The Rust toolchain has to be swapped

Chromium bundles its own rustc, which does not know `aarch64-unknown-haiku`.
`../rust/install-rust-toolchain.sh` puts the patched one in its place. Only
the compiler and its libraries come from that build; bindgen, clippy, cargo,
the crubit support files and the vendored crate sources are Chromium's own
build tools and stay from the bundle.

Two things this surfaced:

* The replacement rustc needs a std for the **host** as well as the target.
  Built with `target = ["aarch64-unknown-haiku"]` alone it has none, and
  Chromium's host build tools fail with `can't find crate for std`.
* `build/rust/std/rules/BUILD.gn` lists all 717 std source files by name,
  generated against the bundled rustc. A different revision has a different
  set. `../rust/sync-std-sources.py` drops the entries whose files are gone --
  four of them here -- rather than inventing any.

### Compiling: where it is now

71 object files built for the Haiku target. The build is inside
PartitionAlloc, stopped at `sys/syscall.h`, which Haiku does not have.

Getting this far took eight source fixes, in three groups.

**The build was targeting the wrong platform.** Chromium hardcodes
`--target=aarch64-linux-gnu` for arm64 on anything that is not Android,
Fuchsia or a ChromeOS device, so every file compiled against clang's Linux
assumptions and libc++ could not resolve `memcpy` from Haiku's `<string.h>`.
Separately, `//build/config/haiku:sdk` existed but was attached to nothing, so
`-D_DEFAULT_SOURCE` never reached the compiler and Haiku's BSD extensions --
`timegm`, `memrchr`, `strchrnul` -- stayed hidden. It is in
`default_compiler_configs` now.

**libc++ needed two fixes, both upstream-shaped.**

* Haiku's ctype is glibc-shaped -- the same `_ISspace`/`_ISprint` names
  reached through `__ctype_b_loc()` -- so it can share that branch outright.
* `__regex_word` picked the big-endian path because the test reads
  `BYTE_ORDER == BIG_ENDIAN` and neither macro is defined at that point;
  the preprocessor treats both as 0 and `0 == 0` is true. Requiring them to
  be defined before comparing fixes it for any libc that does not provide
  them, not only Haiku.
* Haiku's `<ctype.h>` defines `toupper`, `isalpha` and the rest as
  function-like macros with no `__cplusplus` guard, so they swallow the member
  functions libc++ declares. libstdc++ undefines them in its own `<cctype>`
  for exactly this reason; libc++ now does too.

**perfetto keeps its own OS detection** and stops at `#error` for anything it
does not know. Four fixes: the OS branch itself, `CLOCK_BOOTTIME` (absent on
Haiku -- it now falls back to the wall clock, which is what the code already
did when its runtime probe failed), `CLOCK_MONOTONIC_RAW` (tested for rather
than guessed from the platform name), and `timegm` (present in libroot but
declared in `<bsd/time.h>`). Thread ids needed real thought: the generic
fallback casts `pthread_self()` to an integer and Haiku's `pthread_t` is a
pointer, so it now uses `find_thread(nullptr)` -- the small integer Haiku's
own tools display.

**PartitionAlloc keeps a third copy of the platform detection**, separate from
`//build/build_config.h` and from perfetto's. Without Haiku in it,
`PA_BUILDFLAG(IS_POSIX)` was 0 and PartitionAlloc's own logging would not
compile.

### Two decisions worth knowing

**`is_haiku` exists.** `BUILDCONFIG.gn` asks not to add `is_*` variables for
"random lesser-used Unix systems", and for an upstream submission that is
right -- `current_os == "haiku"` says the same thing. Out of tree it is not:
150 files needed the term, and one variable is far easier to keep correct
across rebases than the same comparison spelled out 150 times.

**The gn root is `//chrome:chrome`.** The default, `//:gn_all`, drags in every
test target Chromium has, each with its own platform assumptions. A port has
no use for those yet. `.gn` is not part of the patch -- the applier writes it.

### Where automation was wrong

`fixdeps.py` put Haiku into `third_party/breakpad`'s guard, which sits under a
comment reading `# Mac ---`. That would have built Mac symbol-dumping code.
The right fix was the other way round: exclude Haiku at the two places that
ask for `dump_syms` under `is_posix`, since the tool is only defined for Mac.
Worth remembering when re-running these scripts on a new Chromium revision --
they are fast, not careful.

## The arm64 blocker, and how it was cleared

Chromium's Rust cannot be turned off -- `enable_rust=false` fails at
`//skia:bridge_rust_side`, a hard dependency of the browser -- and Rust had no
`aarch64-unknown-haiku` target: `rustc --print target-list` offered
`i686-unknown-haiku` and `x86_64-unknown-haiku` and nothing else.

`../rust/` adds it. The target spec is 26 lines, std needed no change, and the
result runs on Haiku arm64 -- `HashMap`, threads, `std::backtrace` and
`std::env` all verified in QEMU. See `../rust/README.md`.

With that rustc, `gn gen` for arm64 gets past Rust and stops in the same place
the x64 configuration does. Note that a *stock* rustc still cannot build this
target, so `//third_party/rust-toolchain` has to be pointed at the patched one
before Chromium's Rust targets will link.

## What comes after, on any architecture

`gn gen` for x64 reaches Chromium's feature flags and then
`build/modules/BUILD.gn`: `Unsupported unified modules os: haiku`. Behind that
is the ordinary long tail of a new-OS port -- dozens of `build/config/*` and
`BUILD.gn` sites that enumerate the platforms they know.

Two subsystems have to be written rather than adjusted:

* **Sandbox.** `sandbox/` has exactly three backends: `linux`, `mac`, `win`.
  Haiku has no seccomp-bpf, no namespaces and no setuid helper, so this is a
  stub plus `--no-sandbox`, or a real design.
* **Windowing.** `ui/ozone/platform/` has `cast drm flatland headless wayland
  x11`; none applies to Haiku, whose windows are BeAPI (`BWindow`/`BView`).
  A new Ozone platform is needed. `headless` is the smallest existing one at
  17 files, and is the shape to copy.

For scale: `base/` alone is 3,033 sources carrying 419 `BUILDFLAG(IS_LINUX)`
and 511 `BUILDFLAG(IS_POSIX)` branches. Of the 505,289 files in the tree, 13
mention Haiku, and every one of those is inside a vendored Rust crate.

## Reproducing

```sh
# depot_tools must live on the container filesystem: it takes flock() on its
# own caches, and virtiofs answers that with EAGAIN --
#   Error locking .../gsutil_5.35 (err: [Errno 11] Resource temporarily unavailable)
git clone https://chromium.googlesource.com/chromium/tools/depot_tools /root/depot_tools
export PATH=/root/depot_tools:$PATH

cd /haiku-build/chromium
fetch --nohooks --no-history chromium     # ~27 GB
./port/apply-haiku-port.sh /haiku-build/chromium/src

cd src
./buildtools/linux64/gn gen out/haiku-x64 \
    --args='target_os="haiku" target_cpu="x64" is_debug=false symbol_level=0'
```
