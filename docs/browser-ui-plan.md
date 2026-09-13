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
