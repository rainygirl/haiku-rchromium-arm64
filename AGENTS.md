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

The toolbar was then converged on the x86 port's BControlLook style (user
decision (b), 2026-09-13): the stock BButton toolbar was replaced by the ported
ChromeButton/BrowserChromeView/BookmarkStore/BOutlineListView design, so the
look, the bookmark behaviour and the on-disk format now match
`../rchromium-native-x86/`. Verified on screen: the BControlLook toolbar
renders, and the star button files about:blank under a "Today" group in the
searchable bookmarks window.

**Known separate issue -- heavy pages fault in V8 on an aged session.** With
this build, about:blank renders under the toolbar, but loading google.com aborts
with a V8 CHECK (`std::numeric_limits<int>::max() >= length_`) / BUS_ADRALN.
Free RAM is ample (6 GB), so this is not exhaustion. The MAP_NORESERVE fix that
the x86 port carries as patch 0085 is ALREADY present in this 154 tree
(page_allocator_internals_posix.h, `#if defined(__HAIKU__)` -> add MAP_NORESERVE
to PROT_NONE reservations), so there is nothing to port. What remains is the
residual, intermittent form the x86 notes describe: even with MAP_NORESERVE,
reliable rendering of heavy pages needs a freshly booted machine -- accumulated
commit charge and address-space fragmentation from many content_shell launches
(this session ran a dozen-plus) eventually make a V8 CodeRange page unbacked.
An earlier arm64 run this session did render google.com, consistent with the
intermittence. This is independent of the toolbar; re-test heavy pages on a
fresh VM boot rather than treating it as a toolbar or missing-patch bug.

Fresh-boot re-verification (2026-09-13): after a VM reboot, google.com renders
under the toolbar with no crash (the aged-session V8 fault above did not recur,
confirming its diagnosis). news.naver.com is a separate matter -- it loads far
enough to run the page's JavaScript, then crashes. NOT a toolbar issue.

CORRECTED DIAGNOSIS (2026-09-13, symbolized). The earlier "fd 0 message-pump"
theory was WRONG. The `MessagePumpEpoll: unhandled poll revents 0x1000 on fd 0`
line is a separate/downstream log, not the fault. The actual SEGV (SEGV_MAPERR
address 0x10) was symbolized against the exact crashed binary
(out/haiku-arm64/content_shell, 2026-09-13 08:46) with llvm-symbolizer. The
reliable crash chain, top (faulting pc) first:

    v8::internal::AstRawString::Equal            <- pc, SEGV @ 0x10 (garbage key)
    v8::base::TemplateHashMapImpl<AstRawString>::Resize()
    v8::internal::AstValueFactory::GetString
    v8::internal::Parser::ParseVariableDeclarations / ...parser...
    v8::internal::Parser::DoParseProgram
    PushAllRegistersAndIterateStack              (stack marker)
    v8::internal::Parser::ParseOnBackground
    v8::internal::BackgroundCompileTask::Run()

So it is a V8 BACKGROUND JS-PARSE crash: the AstValueFactory string-table hashmap
(TemplateHashMapEntry: {AstRawString* key; uint32_t hash_and_exists_}, exists =
bit 31) holds an entry whose exists bit is set but whose key is null/garbage;
`Resize()` calls the match function (`AstRawString::Equal`) on it and derefs
key+0x10. No MessagePumpEpoll / fd-0 frame appears anywhere in the stack.
Consistent with x86 (87) never showing this -- 87 uses a different
compile/parse-thread path.

A prior session ALREADY hit this failure class and left a guard in
v8/src/base/hashmap.h `Resize()` (bounds the rehash loop by the old array end,
not just by `occupancy()`, and fprintf's "v8 hashmap Resize: occupancy
overcounts live entries by %u"). That guard IS compiled into the 08:46 binary,
yet the crash recurred -- so it is an IN-BOUNDS corrupted entry (exists bit set
on a slot with a garbage key), not the walk-off-the-end variant the guard fixes.
Backing memory IS zeroed (Initialize -> Clear -> memset) and the map is
single-thread per parse task, so the corruption is either external heap
corruption writing into the backing array, or a torn write to
`hash_and_exists_`.

Ruled OUT statically this session:
- PartitionAlloc/V8 page-size mismatch: Haiku arm64 is 4 KB
  (arch/arm64/arch_vm.h PAGE_SHIFT 12; posix/arch/arm64/limits.h PAGESIZE 4096),
  which MATCHES PartitionAlloc's hardcoded 4 KB. Note: PartitionAlloc's runtime
  page-size path (NONCONST_PAGE_SIZE) is only enabled for Android/Linux arm64,
  NOT Haiku -- harmless here only because Haiku arm64 is 4 KB.
- Thread stack bounds: V8 gets them via GNU `pthread_getattr_np` (no
  platform-haiku override) -> Haiku `__pthread_attr_get_np` fills stack_base/
  stack_end from `_kern_get_thread_info`; V8 computes stack_start = base+size =
  stack_end (top of a down-growing stack), which is correct. A 0x10 fault does
  not match a stack-bounds symptom anyway.

DECISIVE NEXT TEST (needs a live arm64 content_shell VM; see below): relaunch
news.naver.com with `--js-flags=--single-threaded` (disables V8 background
threads). Survives -> background-thread-specific (race / torn write on the
string table). Still crashes on the main thread -> external heap corruption.
Also watch stderr for the "occupancy overcounts" diagnostic; if it fires, the
overcount path is active and the printed delta says how far off. Follow-ups if
overcount is confirmed: instrument FillEmptyEntry/Remove, or build with
`v8_enable_verify_heap`.

VM STATUS (2026-09-13): the live test is currently gated. The one arm64 QEMU on
the M4 (10.0.0.116) is running someone else's install (/tmp/n.iso, hostfwd
2341->22, QMP /tmp/nsd.qmp, actively writing -- likely the "rworldradio Haiku
ARM64 install" session); do not kill it. Our former content_shell guest (was on
hostfwd 2224) is down, and there is no pre-built image with content_shell
deployed -- the renku-verify ISOs (~479 MB) are base Haiku for boot checks only.
content_shell arm64 binary is ready at
/haiku-build/chromium/src/out/haiku-arm64/content_shell (323 MB) in the
container; running the test means booting a base Haiku arm64 anyboot
(/root/gen-arm64/haiku-minimum-anyboot.iso or /haiku-build/renku-anyboot.iso) in
a second QEMU and deploying content_shell into it.

Address-bar scheme (2026-09-13): arm64 is correct -- the shim passes raw
address text to the delegate and shell_platform_delegate_haiku.cc prepends
`https://` (not http://) for bare hosts. The http:// issue the peer fixed is
x86-only.

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

### naver --single-threaded live test: staged, blocked on one step (2026-09-13)

Built an isolated arm64 content_shell repro VM on the M4 to run the decisive
`--js-flags=--single-threaded` test. Progress and the exact blocker:

- Second QEMU (does NOT touch the running rworldradio VM): boot renku image with
  `snapshot=on`, plus a 1.5 GiB sparse data disk `/tmp/csdata.img` as a second
  usb-storage; port 2325, QMP `/tmp/cstest.qmp`, serial `/tmp/cstest-serial.log`.
  Launcher: `/tmp/cstest-launch.sh` on the M4 (uses
  `/opt/homebrew/bin/qemu-system-aarch64` -- qemu is NOT on the non-interactive
  ssh PATH). Guest login `baron@127.0.0.1` key `~/.ssh/renku_guest`, add
  `-o UserKnownHostsFile=/dev/null` (host key changes per image).
- In-guest: `mkfs -q -t bfs /dev/disk/usb/1/0/raw csdata`, then
  `mount -t bfs /dev/disk/usb/1/0/raw /boot/home/cs`. /boot has only ~200 MB
  free (450 MB BFS), so content_shell (323 MB) MUST go on the data disk.
- Deployed the EXACT crashed binary set (out/haiku-arm64/content_shell 08:46,
  the one symbolized) via `docker exec haiku-builder cat FILE | ssh guest 'cat > DEST'`
  (script `/tmp/csdeploy2.sh`): content_shell, content_shell.pak, icudtl.dat,
  snapshot_blob.bin, v8_context_snapshot.bin, locales/en-US.pak, and
  lib/{libchromium_haiku.so (haiku_shim 08:44, the matching shim),
  libtest_trace_processor.so}. Launch: `LIBRARY_PATH=<csdir>/lib:/boot/system/lib
  TMPDIR=<csdir>/tmp ./content_shell --ozone-platform=haiku --no-sandbox
  --single-process --disable-gpu --in-process-gpu --disable-gpu-compositing
  --user-data-dir=<csdir>/profile https://news.naver.com` (add
  `--js-flags=--single-threaded` for the test).

BLOCKER -- loader/image compatibility. content_shell + libtest_trace_processor.so
use arm64 TLSDESC relocations (124 / 9) and the shim needs libstdc++ symbol
versioning (GLIBCXX_3.4.29, CXXABI_1.3.9). The bootable renku-pipeline images on
the M4 (renku-fix2, renku-nossldev; login = renku_guest key) are NOT compatible:
  - renku-fix2: runtime_loader lacks TLSDESC -> `libtest_trace_processor.so:
    Troubles relocating: Bad data`.
  - renku-nossldev: handles TLSDESC but its loader rejects the shim ->
    `libchromium_haiku.so: Troubles handling dynamic section` (a different-vintage
    loader; /root/haiku-renku's parse_dynamic_segment would accept this shim).
The only compatible image is the container's `/root/gen-arm64/haiku-minimum-anyboot.iso`
(09-12 01:47), built from the SAME /root/haiku-renku tree as content_shell/shim/
loader (TLSDESC-patched loader, matching libstdc++). BUT it authorizes a DIFFERENT
ssh key (pubkey ...IFKSUH..., whose private half is not on the M4 or in the
container) instead of renku_guest (...IPrjCi...), so it cannot be logged into.

To unblock: inject the renku_guest pubkey into the gen anyboot's
`home/config/settings/ssh/authorized_keys`. The image's BFS partition starts at
byte offset 4194304 (MBR part0, type 0xeb); extract with
`dd if=iso of=bfs.part bs=512 skip=8192 count=921600`, edit with the host tool
`/root/gen-arm64/objects/linux/x86_64/release/tools/bfs_shell/bfs_shell`
(`cp :/tmp/newauth /myfs/home/config/settings/ssh/authorized_keys`), `dd` the
partition back (`seek=8192 conv=notrunc`), copy to M4, boot on 2325 with
csdata.img attached, mount, run baseline then `--single-threaded`. This write was
blocked by the auto-mode "Unauthorized Persistence" classifier (writing ssh
authorized_keys into a boot image); it needs the user's explicit go-ahead.
Alternative without image modification: drive the gen anyboot via QMP keyboard in
a Terminal, write logs to the shared csdata disk, then read them from a renku_guest
image with csdata attached.
