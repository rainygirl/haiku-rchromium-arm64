# R Chromium arm64 -- development notes

The AArch64 port. Read this before changing anything under `arm64/`.

## Non-negotiable goal

A Chromium browser that runs on Haiku/AArch64 at native Apple Silicon speed and
is installed like a real application on the RENKU arm64 image. As with x86, GN
success or a bare window is not completion: a real page rendered in a Haiku
window, installed on the Desktop with the blue Chromium icon, and no Qt.

## Where it actually stands (verified 2026-09-13)

**The native BeAPI toolbar works end to end on the RENKU arm64 VM.**
`content_shell` (Chromium 154) renders google.com in a Haiku window under a
hand-built toolbar drawn with BeAPI controls: icon-only Back/Forward/Reload,
add-bookmark and show-bookmarks buttons, and an address field. Verified by
screenshot and by driving it: typing a URL navigates (Shell::LoadURL), the
address field tracks the current URL, Back/Forward enable-state toggles both
ways, and re-navigation (including Back to a previously loaded page) repaints
cleanly -- the x86 localStorage re-navigation stall does not reproduce on 154
for these pages. Single window, no in-content views toolbar.

Launch flags that work on the VM (software render, single process):
`--ozone-platform=haiku --no-sandbox --single-process --disable-gpu
--in-process-gpu --disable-gpu-compositing --user-data-dir=<writable>`; set
`TMPDIR` and `LIBRARY_PATH` (including the dir holding libchromium_haiku.so) to
a writable volume, since /boot is small.

Below is the earlier bring-up state, kept for context; the port README in
`port/README.md` stops at "`//base` builds" (early September) and is well behind.

- **The full `//chrome` target builds.** Chromium **154.0.8036.0**, `target_os=
  haiku target_cpu=arm64`, produced `out/haiku-arm64/chrome` (~497 MB, 2026-09-12
  11:54) in the `haiku-builder` container on the Mac mini M4 (`10.0.0.116`).
  This is the whole browser, not `content_shell`.
- **It runs and renders on the RENKU arm64 VM.** Launched from
  `/chromium/apps/Chromium/Chromium` with `--no-sandbox
  --remote-debugging-port=9222`; google.com and news.naver.com render (Korean
  layout, fonts, live cards). Screenshots exist under `~/Workspace/haiku/renku-*.png`.
- **`readelf -d` on the binary lists libbe/libroot/libnetwork/libchromium_haiku,
  no Qt.** The Qt boundary holds here for free -- this port never had Qt.
- **An hpkg was staged** (`chromium-154.0.8036.0-1-arm64.hpkg`, ~158 MB,
  2026-09-11) with the `packaging/Chromium.PackageInfo` metadata.

### What this is NOT yet

- **Not installed.** On the VM, `/chromium` is a manual scratch mount from a raw
  disk image; the browser is launched by hand over SSH. It is not in
  `/boot/system/apps`, not in the Deskbar Applications menu, and the hpkg is not
  in any repository. `.PackageInfo` on the mount is a zero-filled placeholder.
- **Not branded.** The window title bar and Deskbar entry say "Chromium", the
  icon is the stock one, and the signature is `application/x-vnd.Chromium-Ozone`.
  The blue R Chromium icon (`../assets/rchromium.hvif`), the name and an app
  signature have not been applied.
- **Not the R Chromium UI (and this is now the main job).** Today it is Chrome's
  own toolbar, omnibox and bookmarks. The decision (2026-09-13) is to converge
  both platforms on one product: `content_shell` wrapped in a hand-written BeAPI
  toolbar, implemented here on arm64 first and then ported to x86. That means
  dropping the `//chrome` target for `//content/shell:content_shell` and building
  the native UI. See `docs/browser-ui-plan.md`.

## How this port is put together

Four layers, each with its own build:

1. **Cross toolchain** (`toolchain-build/`). There is no prebuilt Haiku arm64
   toolchain, so the container cross-builds the sysroot, Python 3.14 and its
   libraries, gn/ninja, and clang/lld 19.1.7, packaging each as an arm64 hpkg
   the image build can consume.
2. **Rust** (`rust/`). Chromium's Rust cannot be disabled (`//skia:bridge_rust_side`
   is a hard dependency) and stock rustc has no `aarch64-unknown-haiku` target.
   `rust/` adds the 26-line target spec and swaps in a patched rustc;
   `//third_party/rust-toolchain` must point at it.
3. **The Haiku port** (`port/`). `apply-haiku-port.sh` turns `__HAIKU__` into
   `OS_HAIKU`/`IS_HAIKU`, adds a target OS and toolchain, and applies source
   fixes; `port-ozone.py` registers the Ozone platform and copies the BeAPI
   backend into `ui/ozone/platform/haiku`. `port/README.md` has the detail on
   what `//base` needed (epoll->poll, int_fast8_t, the POSIX-not-Linux long tail).
4. **The BeAPI shim** (`haiku_shim/`). `BWindow`/`BView` subclasses cannot live
   in Chromium's `-fno-rtti` clang objects -- libbe runs `dynamic_cast` on every
   window message and a null `type_info` faults. They are compiled with the gcc
   that built libbe into `libchromium_haiku`, which the ozone `source_set` links
   via `libs = [ "be", "chromium_haiku" ]`.

Plus the **`A0001` runtime_loader TLSDESC** kernel patch in
`../haiku_kernel_patches/`: clang emits `R_AARCH64_TLSDESC` and Haiku's loader
did not handle it, so nothing with a `thread_local` loaded until this landed.

## Reconciliation done in this restructure (2026-09-13)

The port generator had drifted from what actually built. `port/files/ozone/haiku/`
was the early-September staging (no `haiku_beapi`, no `haiku_shim`), while the
M4 container's `ui/ozone/platform/haiku/` carried the debugged 2026-09-12
sources. The applied sources were pulled back into `port/files/` so the
generator reproduces the working tree:

- `port/files/ozone/haiku/` updated to the Sep-12 sources; `haiku_beapi.{cc,h}`
  and `haiku_shim.h` added.
- `port/files/media/audio/haiku/audio_manager_haiku.cc` added (was never staged).
- `port/files/build/config/haiku/` and `.../toolchain/haiku/` updated to the
  Sep-12 versions.

Still not captured mechanically: any edits made directly in the M4 `src/` tree
outside these directories (the port scripts only regenerate what they name).
`port/haiku-port.diff` remains an early snapshot, not the source of truth -- the
scripts are. A clean-checkout reproduction has not been re-run since this
reconciliation; do that before trusting it.

## Remaining work

The headline job is the BeAPI native UI (decided 2026-09-13). It, and the
install/branding that follow, need the M4 container and a running RENKU arm64
image, which are driven from other sessions.

1. **Native BeAPI toolbar on content_shell -- DONE and running on the VM
   (2026-09-13).** Compile-verified and then verified live:
   - the toolbar itself in the shim (`haiku_shim.cc`: Back/Forward/Reload
     BButtons + address BTextControl + content-view inset) -- compiles and links
     into libchromium_haiku.so;
   - the ozone wiring (`haiku_toolbar_bridge.{h,cc}`, `haiku_beapi`,
     `haiku_window`) that carries toolbar events to the UI thread and pushes
     state back;
   - `content/shell/browser/shell_platform_delegate_haiku.cc`, selected by
     `port-content-shell-ui.py`, turning toolbar events into GoBackOrForward/
     Reload/Stop/LoadURL and pushing address/loading/enabled state down.
   Built as a full `content_shell` (root switched from //chrome:chrome; two
   POSIX-not-Linux fixes captured in port-content-shell-build.py) and run on the
   VM. Buttons currently use Unicode glyphs; true HVIF icon art is still a
   refinement. The bookmarks store/window are wired and compile, but were not
   exercised on screen yet. Remaining under this item: HVIF icons; an on-screen
   bookmarks test; then the x86 (Chromium 87) backport. Full plan and the
   CH154-vs-CH87 deltas: `docs/browser-ui-plan.md`.
2. **Brand it.** Apply `../assets/rchromium.hvif`, set the app name to R Chromium
   and a real signature, so it is not stock "Chromium".
3. **Install into the image.** Rebuild the hpkg **zlib-compressed, not zstd**
   (zstd hpkg files install silently empty on this kernel -- check bytes 18-19,
   `0001` zlib / `0002` zstd), verify `readelf -d NEEDED` against a known-good
   reference (a package's `requires:` does not prove the binary's `DT_NEEDED`),
   then deploy through `~/Workspace/renku-arm64/make-renku-repo.sh` to
   `renku-repo.coroke.net/arm64`, or bake it into the image definition.
4. **Make it appear in the Deskbar.** Promote the binary's icon and signature
   from resources to attributes (`resattr`), then `mimeset`; Deskbar reads
   attributes, not resources.
5. **Sandbox.** Currently `--no-sandbox` (no seccomp/namespaces/zygote on
   Haiku). Structural: a real design or an accepted limitation, documented.
6. **Re-run a clean-checkout build** after the reconciliation above and record
   the exact `gn gen`/`ninja` invocation and revision that reproduces the binary.

## The x86 sibling already has its own native toolbar

`../rchromium-native-x86/` is NOT a backport target: it independently grew an
equivalent native toolbar (Chromium 87), implemented with BControlLook-drawn
buttons (`chromium87_overlay/ozone/haiku_beapi_views.cc`, `haiku_browser_chrome.h`)
plus the aura ShellPlatformDelegate. Both platforms meet the same user spec
(icon toolbar + address field + date-grouped searchable bookmarks + blue-icon
Desktop install) and share the same design concepts -- a widget-keyed bridge so
content_shell never sees a BeAPI type, an explicit platform_->aura->ShowWindow()
in the delegate, and the SetAddressBarURL/SetIsLoading/EnableUIControl mapping.

They differ only in how the toolbar is drawn (this port: stock BButton via the
shim; x86: custom BControlLook drawing) and cannot share source across the 87 vs
154 API gap. Whether to converge the two on one style is an open user decision;
until it is made, neither is a port of the other. Do not rewrite one to match
the other without that decision.

## Relationship to renku-arm64, and deployment

This repository is the **canonical source** for the arm64 Chromium port. The
RENKU image builder consumes a Chromium port too, and today that is a **separate
copy** at `~/Workspace/renku-arm64/chromium/` (its `docker-build-renku-arm64.sh`
copies that directory into the build container). The two can drift.

The agreed plan (2026-09-13) resolves the drift in this order:

1. Implement the native BeAPI UI here first (see `docs/browser-ui-plan.md`).
2. Publish this repository to GitHub once the native UI works.
3. Point renku-arm64 at the published GitHub repo -- clone or submodule in the
   image build -- instead of its local `chromium/` copy.

Until step 2, do not rewire renku-arm64. Treat this repository as the source of
truth: any fix made in the renku-arm64 copy should be mirrored back here, not the
other way round. `~/Workspace/renku-arm64/chromium/SOURCE.md` records the same
intent on that side.

## Traps worth keeping

- **`is_haiku` is defined out of tree on purpose.** `BUILDCONFIG.gn` asks not to
  add `is_*` for lesser Unixes, but 150 files needed the term; one variable
  rebases better than the comparison spelled 150 times.
- **The gn root is `//chrome:chrome`,** not `//:gn_all`, to avoid dragging in
  every test target's platform assumptions.
- **hpkg `vendor` must be exactly `Haiku Project`** or `package_repo` refuses
  the index; `users` is a single line, not a brace block; adding a package
  changes the repo checksum so jam needs `HAIKU_NO_DOWNLOADS=1`.
- **Cross-built binaries can carry an absolute sysroot path in `DT_NEEDED`;**
  `patchelf` reduces those to a basename. Check `readelf -d` right after any
  large link.
- **`git`/other tooling is not present in the container tree** the way it is on
  the Haiku box; the M4 `src/` is not a git checkout, so there is no diff to
  read -- the port scripts are the only record of what was changed.

## AI disclosure

This port and these notes were produced largely with Claude Code.
