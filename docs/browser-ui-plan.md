# Browser UI plan (arm64-first): a native BeAPI toolbar on content_shell

Decision (2026-09-13, from the user): both platforms converge on **one product**
-- Chromium `content_shell` wrapped in a hand-written Haiku-native (BeAPI)
browser UI, the same design `../../rchromium-native-x86/docs/browser-ui-plan.md`
lays out. It is implemented **here on arm64 first** -- modern Chromium (154),
native build speed on Apple Silicon, easy iteration -- and then **ported back to
x86** (Chromium 87) once it works.

## What this changes for arm64

The arm64 port currently builds the full `//chrome` browser, which ships
Chrome's own toolbar, omnibox and bookmarks. That is thrown away for this: the
UI goal is R Chromium's icon-only Back/Forward/Reload, an address field, and
date-grouped searchable bookmarks, drawn with BeAPI controls -- not Chrome's
Views UI.

Concretely:

1. **Switch the build target to `//content/shell:content_shell`.** Change the
   `.gn` root (currently `//chrome:chrome`) or build the target directly. The
   Haiku Ozone backend (`port/files/ozone/haiku/`) already puts a real `BWindow`
   with a `HaikuContentView` on screen and renders into it, so content_shell +
   ozone should come up as a bare window before any UI is added.
2. **Add a Haiku ShellPlatformDelegate.** content_shell selects its platform UI
   through `ShellPlatformDelegate`; the aura delegate (built by default) creates
   a `WindowTreeHost` and no chrome. Replace it with a
   `shell_platform_delegate_haiku.cc` that keeps aura for content hosting and
   adds native chrome to the `BWindow` the ozone layer already owns.
3. **Toolbar and address bar** as BeAPI controls (`BButton` icon-only,
   `BTextControl`), wired to `Shell::GoBackOrForward`/`Reload`/`Stop`/`LoadURL`.
4. **Bookmarks**: file-backed storage grouped by date, plus a searchable list.
5. **Branding + install**: the blue `../assets/rchromium.hvif` icon, the name,
   an app signature, and a Deskbar entry (attributes, not resources).

The architecture-neutral design -- where the UI attaches, the ozone top-inset
for the toolbar, and the BWindow-looper vs Chromium-UI-thread threading
constraint (the part that bites) -- is already worked out in the x86 plan and
applies unchanged. Read that document for the delegate hooks, the inset
mechanism, and the post-to-UI-thread / post-to-looper pattern.

## CH154 vs CH87 deltas to expect

The x86 design was read off Chromium 87 sources; arm64 is 154. Before following
it line by line, re-check against the 154 checkout:

- `ShellPlatformDelegate`'s method set and signatures (`CreatePlatformWindow`,
  `SetContents`, `EnableUIControl`, `SetAddressBarURL`, `SetIsLoading`,
  `SetTitle`, `GetNativeWindow`) -- confirm they still exist and match.
- `Shell`'s public API (`LoadURL`, `GoBackOrForward`, `Reload`, `Stop`,
  `UpdateNavigationControls`, `ActionPerformed`, `URLEntered`).
- Whether 154 content_shell still uses the aura delegate the same way, and
  whether `base::string16` (87) is now `std::u16string`.
- `HaikuContentView::AttachedToWindow` fills the whole window today; the toolbar
  needs a geometric top inset, with `GetBounds` reporting the content area.

## Order of work

1. Build `content_shell` for arm64 and confirm a page renders in the BWindow
   before adding any UI. This isolates ozone from UI bugs.
2. Geometric top inset in the ozone layer; verify the page renders shifted down.
3. Toolbar controls wired through the post-to-UI-thread pattern.
4. Delegate hooks (`SetAddressBarURL`, `SetIsLoading`, `EnableUIControl`,
   `SetTitle`), each posting to the looper.
5. Bookmarks: storage, then searchable UI.
6. Branding + Desktop/Deskbar install.
7. **Port to x86.** Once the delegate and toolbar work on 154, backport to the
   Chromium 87 tree in the x86 repo, adjusting for the API deltas in reverse.

## Not done in this session

This is the implementation plan; no UI code was written or built here. The work
needs the Chromium 154 checkout in the M4 `haiku-builder` container and a running
RENKU arm64 image. A first `shell_platform_delegate_haiku.cc` should be seeded
against the actual 154 content_shell headers, not guessed.

## Known hazard to verify: re-navigation of heavy pages

From the x86 content_shell session (rchromium-native-9c, 2026-09-13): initial
page load was made reliable (6/6), but **re-navigating the same window to a
different heavy page** -- via `Shell::LoadURL` or the address bar -- does not
render reliably. news.google.co.kr re-renders on re-navigation; news.naver.com
leaves a blank screen or the previous page's content. It is not a crash.

The toolbar's address field and Reload button exercise exactly this path, so
make re-navigation an acceptance test from the start, not an afterthought:

- After the toolbar works, alternate the same window between two heavy sites
  (news.naver.com <-> news.google.co.kr) several times and confirm each load
  actually paints, not just the first.
- Suspect the compositor/frame-sink re-attach on navigation (see the x86 patches
  0084 queue-early-compositor-frame-sink-requests and 0086 ignore-cancelled-
  frame-delete for the shapes already seen) and the `HaikuContentView` re-use
  across navigations.

Catching this on arm64 first means the x86 backport does not meet it twice.

### Root cause (found on x86, 2026-09-13)

The x86 session traced it with stackwalk.c, catching the renderer main thread
right after a re-navigation:

    StorageController::ResetStorageAreaAndNamespaceConnections
     -> StorageNamespace::ResetStorageAreaAndNamespaceConnections
      -> CachedStorageArea::ResetConnection -> EnsureLoaded
       -> StorageAreaProxy::GetAll            (synchronous mojo call)
        -> InterfaceEndpointClient::SyncWatch -> WaitableEvent::WaitMany
         -> ConditionVariable::Wait           (blocks forever)

Navigation resets the storage connections (OnStorageServiceDisconnected ->
RecoverFromStorageServiceCrash -> ResetStorageAreaAndNamespaceConnections) and
the renderer re-reads its localStorage area with a *synchronous* GetAll that
never returns. There is no dedicated storage thread here: RunInProcessStorage-
Service runs on a base::ThreadPool sequence, and on 2 cores the renderer main
thread blocks waiting for a storage sequence that never gets scheduled (the
ThreadPool workers are busy with NetworkService etc.). naver uses localStorage
heavily and reproduces it; light google news passes -- matching the symptom.

This is separate from the initial-load stall (fixed with
--disable-gpu-compositing) and the frame-delete race (x86 patch 0086). Fixing
it means making that storage read non-blocking, or guaranteeing the in-process
storage sequence runs ahead of the blocked renderer -- neither trivial.

**Chromium 154 may have made these storage interfaces more asynchronous, so it
may not reproduce here.** If arm64's naver<->google re-navigation paints every
time, the bug is x86-specific and only needs attention during the backport.
Source: rchromium-native-9c (x86 session).
