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

### naver --single-threaded live test: TLSDESC loader blocker SOLVED, shim blocker + Docker wedge (2026-09-13, later)

Pushed the live-test setup much further. Key results:

TLSDESC LOADER FIX (reusable). content_shell (124 R_AARCH64_TLSDESC relocs) and
libtest_trace_processor.so (9) need a runtime_loader with TLSDESC support. The
renku-verify boot images on the M4 (renku-fix2, renku-nossldev; login = baron +
~/.ssh/renku_guest) have loaders that LACK it ("Troubles relocating: Bad data").
The gen-arm64 anyboot (/root/gen-arm64/haiku-minimum-anyboot.iso) has a TLSDESC
loader but is a "minimum" profile that hangs at the boot splash in QEMU (never
reaches userland/network/sshd), so it is unusable for a networked test. Fix:
graft the TLSDESC loader into a renku-verify image's haiku.hpkg. Steps (all in
the haiku-builder container, which has 846G free vs the M4's ~2G):
  1. Copy renku-nossldev.iso into the container; parse MBR part0 (type 0xeb, LBA
     8192 = byte offset 4194304); `dd ... skip=8192 count=921600` to /tmp/noss.part.
  2. Rebuild the loader from CURRENT source (the checked-out
     src/system/runtime_loader/elf_load_image.cpp is NEWER than the prebuilt
     00:59 loader, so use jam, not the stale binary):
     `cd /root/gen-arm64 && /haiku-build/buildtools/jam/bin.linuxx86/jam -q -j1 runtime_loader`
     -> objects/haiku/arm64/release/system/runtime_loader/runtime_loader.
  3. Replace it inside the image's haiku pkg with the host package tool:
     `package add -f -C <dir> /tmp/haiku_noss.hpkg runtime_loader` (the loader is
     at package path "runtime_loader", TOP level = /boot/system/runtime_loader,
     NOT "system/runtime_loader"). Extract/put the hpkg with bfs_shell
     (`cp /myfs/system/packages/haiku-...hpkg :/host`, and back), always issue
     `sync` before `quit` (bfs_shell's unmount reports "busy" but sync flushes).
  4. dd the partition back into an iso copy (`seek=8192 conv=notrunc`), copy the
     iso to the M4, boot on 2325 with csdata.img attached.
Result: the grafted image BOOTS in ~40s to sshd (loader<->libroot ABI across
hrev99000 libs + hrev99002+175 loader is compatible), and content_shell now gets
PAST libtest_trace_processor.so (TLSDESC resolved). So the TLSDESC blocker is
solved. Host tools: bfs_shell/package/anyboot at
/root/gen-arm64/objects/linux/x86_64/release/tools/.

OPEN BLOCKER -- the shim fails to load: `libchromium_haiku.so: Troubles handling
dynamic section`. Instrumented the loader (FATAL uses dprintf -> guest
/var/log/syslog, and printf to stdout only while !gProgramLoaded, so read the
guest syslog, not just the app's stderr). syslog shows `runtime_loader: DBG no
symhash` -> parse_dynamic_segment's `if (!image->symhash) return false` fires:
image->symhash is null for the shim even though `readelf -d` shows it HAS DT_HASH
(0x120) (and, after relinking with `-Wl,--hash-style=both`, GNU_HASH too). The
DT_HASH case sets symhash = d_ptr + regions[0].delta, which should be non-null.
content_shell and libtest (both have DT_HASH + GNU_HASH) load fine; only the
gcc-built, libstdc++/symbol-versioned shim hits this. NOT yet root-caused --
needs runtime tracing of the dynamic-tag loop for the shim (print each d_tag +
the symhash assignment). The shim relinked with GNU_HASH is at
container:/tmp/libshim_gnu.so; deployed at csdata:/boot/home/cs/lib/.

INFRA: Docker Desktop's engine wedged after many rapid `docker exec` streams
(even `docker version`/`docker ps` hang; `killall Docker; open -a Docker` from
SSH relaunched the app - 22 procs - but the engine did not come back, likely
needs a Mac GUI restart of Docker Desktop). All container work is blocked until
Docker is healthy. Artifacts persist in the container's writable layer; the last
good grafted+debug image is on the M4 at /tmp/nossdbg.iso, csdata.img holds the
deployed content_shell. Launcher /tmp/cstest-launch.sh (ISO= line points at the
image; boot on port 2325, QMP /tmp/cstest.qmp).

NOTE on the ultimate fix: even once content_shell runs and --js-flags=
--single-threaded confirms the hypothesis, the actual V8 fix needs a Chromium
rebuild (a second ninja), which the port rules forbid in this state -- so the
diagnostic is the deliverable here, and the fix itself is a follow-up build.

### naver --single-threaded live test: DONE. Shim-load fixed, decisive results (2026-09-13, resolved)

The live test ran to completion. Two loader blockers were fixed, then the
decisive experiments were run.

SHIM LOAD FIX (root-caused). libchromium_haiku.so failed
`Troubles handling dynamic section`. Instrumented runtime_loader
(FATAL->dprintf lands in the guest /var/log/syslog, not the app's stderr): the
loop in parse_dynamic_segment read `d[0].d_tag==0` immediately, i.e.
image->dynamic_ptr pointed at zeroed memory, so symhash stayed null. Cause: the
shim is gcc-linked and uses ld's default arm64 `max-page-size=0x10000` (64 KB),
which gives its RW LOAD segment a 0x10000 offset<->vaddr skew (LOAD offset
0x215d8 / vaddr 0x315d8; DYNAMIC vaddr 0x32210). Haiku's arm64 runtime_loader
mis-maps that layout so DYNAMIC's mapped address is wrong. clang-built
content_shell/libtest use offset==vaddr and are fine. FIX: relink the shim at
4 KB page alignment (matches Haiku arm64) --
`aarch64-unknown-haiku-g++ -shared haiku_shim.o -Wl,-soname,libchromium_haiku.so
-Wl,--hash-style=both -Wl,-z,max-page-size=0x1000 -lbe -lstdc++ -lroot`. With
that, the shim loads and content_shell runs to the page. (This should be folded
into the shim's real build.)

DECISIVE RESULTS (content_shell running naver on the grafted TLSDESC image):
- Baseline naver: crashes with the same V8 stack as csn2.log (AstRawString::Equal
  <- TemplateHashMapImpl::Resize <- AstValueFactory::GetString <-
  Parser::ParseOnBackground <- BackgroundCompileTask::Run). Repro confirmed.
- `--js-flags=--single-threaded`: STILL crashes, identical stack -> NOT a
  background-thread race / torn write.
- Free RAM at crash ~4.0 GB of 4.28 GB -> NOT memory exhaustion.
- `--disable-http-cache --v8-cache-options=none` + empty profile: STILL crashes
  -> NOT the disk/V8 code cache or storage path.
- Address-space overlap test (the peer's hypothesis B, run natively on arm64 via
  a cross-compiled C probe): reserve 256 MB PROT_NONE|MAP_NORESERVE, then do anon
  + file mmaps -> ALL land ABOVE the reservation, overlap_hits=0; mprotect RW/RWX
  commit into the reservation works. So on arm64 Haiku, foreign mmaps never land
  inside a V8/PA-style reservation -> hypothesis B is REFUTED on arm64. (It may
  still hold on x86, which is 32-bit / ~2 GB user space and address-cramped; the
  x86 session sees a parallel V8 StringTable crash whose fault address is in the
  >2 GB kernel range. Same V8 string-table subsystem, likely DIFFERENT root cause
  per architecture.)

CONCLUSION: the arm64 naver crash is a DETERMINISTIC corruption of V8's
AstValueFactory string_table_ (base::TemplateHashMapImpl) during parse of naver's
heavy JS -- independent of threading, memory pressure, disk/code cache, and
address-space overlap. An entry ends up with its exists bit set but a null/garbage
key (the prior "occupancy overcounts" guard in v8/src/base/hashmap.h Resize is a
symptom of the same thing). Remaining candidates: a V8 arm64 codegen/zone-
alignment bug, or inconsistent AstRawString hashing that makes Probe double-insert
on naver's specific strings. Pinning it needs V8 instrumentation = a Chromium
rebuild (a second ninja), which the port rules forbid in this state -- so this is
the handoff point: root-cause direction established and every environmental cause
ruled out; the fix is a follow-up build task.

Repro env (reusable): grafted TLSDESC image /tmp/nosstrace.iso on the M4 (boot
via /tmp/cstest-launch.sh on port 2325), content_shell + 4 KB-relinked shim on
csdata.img mounted at /boot/home/cs. The arm64 B-probe source is in the session
scratchpad (btest.c) and cross-compiles with aarch64-unknown-haiku-gcc.

### naver crash: ROOT CAUSE confirmed via instrumented rebuild + fix direction (2026-09-13, option 1)

User authorized lifting the no-second-ninja rule for a targeted V8 instrumentation
build. Results:

INSTRUMENTED DUMP (built content_shell with a scan in ast-value-factory.cc
GetString that dumps any string_table_ entry whose key pointer is null/misaligned):
    V8DBG stomped entry: key=0x0 hash=0x7fffffff occ=1639 cap=4096
        map=0x1c009cc000 entry=0x1c009cc000
    V8DBG entry16: 00 00 00 00 00 00 00 00  ff ff ff ff ff ff ff ff
    Received signal 11 SEGV_ACCERR 001c009cbfe0   (reading 0x20 before map base)
Reading: the FIRST entry of the string table's backing (== the allocation base)
is overwritten with {key = 0x0, hash_and_exists_ = 0xffffffff}. The exists bit
(31) is set so it looks "occupied", but key is null -> Resize/Probe feeds a null
key to AstRawString::Equal -> crash. The stomp pattern is 8 bytes 0x00 then 8
bytes 0xFF (= {ptr=0, u64=0xffffffffffffffff}) -- a specific sentinel, not random
heap junk. The page immediately before the backing is PROT_NONE (the -0x20 read
faulted SEGV_ACCERR) -> the backing is the START of a PartitionAlloc slot span.
So: a browser-side write puts {0, -1} at the start of a PA slot that happens to
be the renderer's V8 string-table backing.

MECHANISM confirmed by the three-way process test (both platforms):
  - empty profile path + single-process = renders fine
  - valid profile path + single-process = crash during heavy V8 work
  - valid profile path + MULTI-process  = renderer passes V8, no stomp
=> It is NOT a renderer/V8 internal defect. In single-process a browser-side
subsystem shares the address space and stomps the renderer's V8 heap/zone;
isolating the renderer into its own process removes the stomp.

FIX EXPERIMENTS (arm64):
  - off-the-record main context (ShellBrowserContext(true), shell_browser_main_parts.cc
    :141) -- the x86 session's fix: makes the default storage partition in-memory,
    so on-disk leveldb/disk_cache/etc. never start (verified: the profile dir gets
    only DevToolsActivePort, no Code Cache/LocalStorage/blob_storage/DIPS). On arm64
    this fixes example.com and a data: JS page (100k loop + DOM) -- so off-the-record
    does NOT break JS -- but naver STILL crashes with the same parse stack. So on
    arm64 the stomper is NOT the on-disk storage subsystem; it is an in-process
    browser component active during heavy page load (in-memory storage service,
    network service, or something that scales with the page).
  - MULTI-process (drop --single-process): naver runs with NO V8 crash, NO
    font_cache CHECK (arm64 has standard Haiku fonts in /boot/system/data/fonts/
    {ttfonts,otfonts,psfonts}), only a benign webrtc cpu_info ERROR. This is the
    working arm64 mitigation for the V8 stomp. (Visual render not confirmable on
    renku-nossldev, which boots headless -- sshd but no app_server/desktop.)

STATUS: root cause is a single-process browser-side write of {0,-1} into a PA slot
holding the renderer's V8 string table. off-the-record is insufficient on arm64;
multi-process avoids it. Remaining to fully fix: either (a) identify and fix the
exact browser subsystem doing the stray write (needs writer-side instrumentation),
or (b) ship content_shell multi-process (needs the renderer child-process launcher
to be solid on Haiku; on arm64 it already runs naver without the font/V8 crashes).
The x86 session is pursuing the same on its hardware (its 32-bit JSEntryTrampoline
SIGILL under off-the-record is suspected fragmentation, since arm64 64-bit runs JS
fine under off-the-record).

### naver crash: subsystem bisection (2026-09-14, option 1 continued)

To pin WHICH browser subsystem writes {0,-1}, ran a bisection (all single-process,
off-the-record build; the VM is not confounded -- the negative cases below prove
it, and naver reproduces deterministically):
  - Local 2 MB JS, 60,000 unique identifiers (file://, max string-table pressure,
    NO network): NO crash. => not parse volume / string-table size alone.
  - Same 2 MB JS over HTTP (one network request + heavy parse): NO crash.
    => not "any network".
  - example.com (static, https): NO crash. daum.net (another heavy https portal):
    NO crash. => not general heavy-https.
  - news.naver.com (https, hundreds of concurrent subresources): CRASH, every time,
    same V8 string-table stack (BackgroundCompileTask + PartitionRoot::Alloc).
  - off-the-record (in-memory storage, no on-disk leveldb/cache): still CRASH.
  - multi-process: NO crash.
Conclusion: the trigger is naver-SPECIFIC heavy concurrent load -- many subresources
fetched concurrently WHILE V8 background-parses naver's specific JS -- in a single
address space. A browser-side thread (network-service-class, active for the
concurrent fetches; NOT on-disk storage, NOT parse volume) writes {ptr=0,
u64=0xffffffffffffffff} to the start of a PartitionAlloc slot that happens to hold
the renderer's V8 AstValueFactory string-table backing, corrupting entry[0]
(exists bit set, null key) -> deterministic crash. Isolating the renderer
(multi-process) removes it.

Pinning the exact subsystem/line further needs either ASAN (large/uncertain on
Haiku arm64) or a live write-catch (intractable: dynamic hot victim, async one-shot
foreign write, no gdb/watchpoint timing on the guest). Practical fix remains
multi-process; the deep fix is finding the stray {0,-1} writer in the network/
browser path under concurrent load.

### naver: SOLVED via multi-process (2026-09-14)

Proof the crash is fixed: run content_shell WITHOUT --single-process (multi-process,
renderer isolated) and load news.naver.com. DevTools /json/list on the renderer
reports:
    "title": "네이버 뉴스", "url": "https://news.naver.com/", "type": "page"
i.e. naver's HTML+JS parsed and executed (it set the page title) with NO crash --
the exact page that crashes deterministically in single-process. So the fix does
not need ASAN / the exact stray-write line: isolating the renderer removes the
single-process browser-side stomp of the renderer's V8 string table.

ASAN is not available here (Chromium's bundled clang ships asan runtimes only for
Linux targets, none for aarch64-unknown-haiku; sanitizers.gni has no Haiku), so the
exact writer line stays open -- but it is not needed to make naver work.

FIX to ship: run RChromium arm64 multi-process (drop --single-process). The native
BeAPI toolbar is drawn by the browser process (shim/ozone), the page by the
renderer process, which matches real Chromium's split -- so multi-process is
compatible with the native toolbar. Remaining engineering: make the renderer
child-process launcher solid on Haiku and set multi-process as the default launch.
To confirm visually, boot a desktop-capable arm64 image (the renku-verify images
boot headless -- sshd but no app_server desktop on ramfb -- so screenshots are
black; functional proof is via DevTools as above).

### Shipping multi-process (2026-09-14)

--single-process was never in the port code -- only in the launch commands in this
file. The Haiku child-process launcher is a complete first-class implementation
(content/browser/child_process_launcher_helper_haiku.cc, 135 lines: direct launch,
no zygote/sandbox, GlobalDescriptors fd remap, EnsureProcessTerminated reaping,
priority, OpenFileToShare; sandbox_type.cc has the IS_HAIKU branches). So
multi-process is already supported; the only change to ship is dropping
--single-process from the launch.

CANONICAL LAUNCH (multi-process, the fix -- use this, NOT --single-process):
  LIBRARY_PATH=<csdir>/lib:/boot/system/lib TMPDIR=<writable> \
  content_shell --ozone-platform=haiku --no-sandbox \
    --disable-gpu --in-process-gpu --disable-gpu-compositing \
    --user-data-dir=<writable>
(With --in-process-gpu the viz/display compositor runs in the browser process and
presents through the ozone Haiku surface exactly as in single-process, so the
present-to-BWindow path is unchanged; only the renderer runs in its own process.)

Regression (multi-process, DevTools /json confirms the renderer loaded each page
with no crash): news.naver.com -> title "네이버 뉴스"; www.google.com -> page
target present. No V8 stomp, no font_cache CHECK. The native BeAPI toolbar is drawn
by the browser process (shim/ozone) and the page by the renderer, matching real
Chromium's split, so multi-process is compatible with the native toolbar.

Not yet done: (1) VISUAL confirmation of the composited page in the BWindow --
blocked because the renku-verify images boot headless (no app_server desktop on
ramfb; screenshots are black) and the desktop-capable gen-arm64 anyboot hangs at
the boot splash in this QEMU config; needs a desktop-capable arm64 image or
on-device (renku-arm64) verification. (2) The exact browser subsystem doing the
{0,-1} stray write in single-process (needs ASAN, unavailable on Haiku) -- not
required now that multi-process avoids it.

### CORRECTION (2026-09-14): naver is NOT solved by multi-process -- on-device visual test

The earlier "SOLVED via multi-process" claim was WRONG. It rested on the headless
renku-nossldev test, where DevTools showed the DOM (title "네이버 뉴스") but the
renderer had not reached full render and there was no window to see. The on-device
visual test corrects it.

Method: grafted the TLSDESC runtime_loader into the DESKTOP image renku-arm64.iso
(hrev99002_173; MBR part0 BFS at 4194304; package add the loader into
haiku-...hpkg, same workflow as nossldev), booted it on the M4 with ramfb+QMP and
the content_shell csdata.img as an AHCI second disk (a second USB disk hangs the
splash; AHCI shows as /dev/disk/scsi/0/0/0/raw). renku-arm64.iso boots to a full
Haiku DESKTOP on ramfb (QMP screenshots are real, not black). Login: baron with
the image's key = the LOCAL Mac's ~/.ssh/id_ed25519 (pubkey ...IFKSUH...; the
same key the container bakes), so to ssh from the M4 that private key must be on
the M4.

Real-hardware matrix (QMP screenshots):
                simple data: page          news.naver.com
  single-proc   RENDERS (bg #cfe + <h1>)   CRASH (whole app dies, window gone)
  multi-proc    window+toolbar, content     renderer CRASH (window+toolbar stay,
                BLANK (compositing not       content blank; SEGV_MAPERR ...010)
                delivered to the BWindow)

So:
- The native BeAPI toolbar UI DOES render on device (window, address field showing
  https://news.naver.com/, back/forward/reload/star/menu). Simple pages render in
  single-process. The TLSDESC-loader graft + 4 KB-relinked shim work on device.
- naver's page content does NOT render. The renderer crashes with the V8 string-
  table stomp (SEGV @ +0x10) during heavy background compile of naver's JS, in
  BOTH single-process (whole process dies) and multi-process (renderer dies).
  Because it still crashes with the renderer ISOLATED (multi-process), the stomp is
  RENDERER-INTERNAL V8, not a browser-side write -- correcting the earlier
  "browser-side stomp" reading (that too came from the headless false-negative).
- Not avoided by: process model, --js-flags=--single-threaded, --js-flags=
  "--no-lazy --no-concurrent-recompilation --no-parallel-compile-tasks-*",
  off-the-record/in-memory storage, or disabling http/V8 cache.
- Multi-process additionally does not composite renderer content into the BWindow
  on this port (blank content even for a simple page that single-process draws
  fine) -- a separate cross-process present bug.

Bottom line: naver is still broken. The real fix is the V8 string-table corruption
during heavy background compile (the deterministic {0,-1} stomp of the
AstValueFactory backing), which needs V8-level debugging that is currently blocked
(no ASAN runtime for Haiku; a live write-catch is intractable here). Single-process
renders simple/light pages; heavy pages like naver crash.

### naver crash ROOT CAUSE confirmed: use-after-free of the live V8 string table (2026-09-14)

Traced the naver crash to a definitive use-after-free (NOT a stomp, NOT link
corruption):

- The corrupted "entry" bytes are {0x00 x8, 0xFF x8}. This is exactly a
  PartitionAlloc EncodedNextFreelistEntry for a nullptr next: the default freelist
  is EncodedFreelistPtr; Transform() is ReverseBytes on little-endian, so
  Transform(0)=0 (encoded next), and the shadow is Inverted()=~0=0xffffffffffffffff.
  So a freed PA slot that is the LAST on its freelist (next==nullptr) has first 16
  bytes {0, ~0} -- precisely the observed pattern. The string-table backing is a
  freed PA slot being read as a hashmap entry.
- V8DBG showed the corrupted entry is entry[0] of the CURRENT live map_
  (impl_.map_, == the allocation base, PROT_NONE guard page just before it =
  PA slot start), found by scanning string_table_ at GetString entry. So it is the
  LIVE string_table_ backing that has been freed -- while the AstValueFactory is
  still parsing and calling GetString -- not the old array Resize frees, and not
  after the factory's destruction. Something frees the live map_ slot mid-parse
  (a stray free / double-allocation of that address by other code).
- NOT link corruption: JS executes correctly on arm64 (a data: page computed
  6*7=42 and sum(i^2, i=0..999)=332833500 and rendered them). So the V8 embedded
  builtins blob is intact (unlike the x86 session's link-corruption SIGILL, which
  was its old ld with low-memory flags overwriting the blob -- an x86-only issue).
- PA is not generally broken (JS array allocations work). The UAF is specific to
  naver's heavy load.

The AstValueFactory string_table_ is deep-copied from AstStringConstants'
string_table_ (ctor `string_table_(string_constants->string_table())` ->
TemplateHashMapImpl(const*, ...) allocates a new backing and memcpy's), so it owns
its backing; it is freed in the (defaulted) dtor or in Resize (old array). The
crash reading the CURRENT map_ as freed means an external free of the live slot.

Fix direction: this is a V8/allocator lifetime bug -- a stray free or double-alloc
of the live AstValueFactory string-table backing during heavy background compile
on arm64. Pinning the exact free-site needs allocator-level tracing (log
base::Malloc/base::Free or PA alloc/free of that address with backtraces) or a
dcheck_always_on / PA double-free-detection build -- both heavy rebuilds. The
crash is avoided only by not parsing that much (light pages render fine; heavy
pages like naver crash). Multi-process does NOT help (the UAF is in the renderer's
own V8), and neither do --single-threaded, --no-lazy/--no-parallel-compile,
off-the-record, or cache flags.

### naver on-device: renders intermittently; general UAF, needs ASAN-class tooling (2026-09-14)

On the real renku-arm64 desktop image (renku-arm64.iso, TLSDESC loader grafted into
its haiku hpkg, content_shell on an AHCI-attached csdata.img; boots to the RENKU
desktop on ramfb, QMP screenshots are real):
- news.naver.com RENDERED fully once (native BeAPI toolbar + full naver News: nav
  tabs, news cards, LIVE thumbnails KBS/YTN/MBN, Korean text) with the
  PADBG-instrumented build. But a re-run CRASHED. So it is INTERMITTENT -- a
  Heisenbug, the hallmark of the use-after-free.
- The instrumented build (PADBG PA-free watch + WatchedAllocationPolicy on the
  string table) perturbs the heap enough to sometimes dodge the UAF, sometimes not.
- Crucially, the re-run crash did NOT trip PADBG (which watches only the string-
  table hashmap backing) and instead hit base::Vector::length()'s
  CHECK_GE(INT_MAX, length_) (BUS_ADRALN 0 via OS::Abort). So the corrupted victim
  VARIES (hashmap entry vs Vector length) -- it is a GENERAL use-after-free: a stale
  pointer frees some live V8/base allocation, its slot gets the PA freelist {0,~0},
  and whatever later reads that slot crashes. Not one structure -> watching one
  structure (as PADBG did) cannot catch it.

So a narrow/principled fix (e.g., zone-backing just the string table) would not fix
the general UAF (the Vector victim proves other allocations are hit too). A CERTAIN
fix needs to catch the erroneous free of a live allocation, which requires
ASAN-class tooling (quarantine + redzones + shadow): ASAN has no Haiku runtime
(clang bundles Linux targets only), and the Haiku-native alternatives (build with
use_partition_alloc_as_malloc=false + Haiku guarded/quarantine malloc, or a
PartitionAlloc quarantine/*Scan build) are heavy rebuilds with memory-blowup risk
for a full browser and may themselves perturb the layout. JS itself is correct on
arm64 (6*7=42, sum(i^2,0..999)=332833500 rendered), so this is NOT the x86 session's
link-corruption bug -- that was fixed separately by byte-restoring the V8 embedded
blob; arm64's is a real heap UAF.

State: root cause DEFINITIVELY diagnosed (general renderer-side UAF, freelist {0,~0}
proof + Heisenbug). Native toolbar works; light pages render reliably; heavy pages
like naver render sometimes and crash sometimes. A certain fix is gated on getting
ASAN-class UAF tooling onto Haiku arm64 (a real porting effort), or landing an
upstream V8 lifetime fix once the culprit is identified with such tooling.
