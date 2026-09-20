// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// R Chromium's Haiku ShellPlatformDelegate. It keeps content_shell's aura
// content hosting -- the ozone Haiku backend renders the page into the BWindow
// through the aura WindowTreeHost -- and adds the native BeAPI toolbar that the
// ozone layer draws, wired to Shell navigation through the toolbar bridge.
//
// This replaces shell_platform_delegate_aura.cc when is_haiku; it therefore
// provides the same out-of-line ShellPlatformDelegate definitions the aura
// file does, plus the toolbar wiring.

#include "content/shell/browser/shell_platform_delegate.h"

#include <memory>
#include <string>

#include "base/functional/bind.h"
#include "base/location.h"
#include "base/logging.h"
#include "base/memory/raw_ptr.h"
#include "base/memory/weak_ptr.h"
#include "base/strings/utf_string_conversions.h"
#include "base/task/sequenced_task_runner.h"
#include "base/time/time.h"
#include "content/public/browser/render_widget_host_view.h"
#include "content/public/browser/web_contents.h"
#include "content/shell/browser/shell.h"
#include "content/shell/browser/shell_platform_data_aura.h"
#include "ui/aura/env.h"
#include "ui/aura/window.h"
#include "ui/aura/window_event_dispatcher.h"
#include "ui/aura/window_tree_host.h"
#include "ui/aura/window_tree_host_observer.h"
#include "ui/ozone/platform/haiku/haiku_toolbar_bridge.h"
#include "url/gurl.h"

namespace content {

namespace {

// One per Shell. Receives toolbar events (on the UI thread, posted by the
// ozone bridge) and turns them into Shell navigation.
class ShellToolbarObserver final : public ui::HaikuToolbarObserver {
 public:
  explicit ShellToolbarObserver(Shell* shell) : shell_(shell) {}

  void OnNavigateBack() override { shell_->GoBackOrForward(-1); }
  void OnNavigateForward() override { shell_->GoBackOrForward(1); }

  void OnReloadOrStop() override {
    if (shell_->web_contents() && shell_->web_contents()->IsLoading()) {
      shell_->Stop();
    } else {
      shell_->Reload();
    }
  }

  void OnNavigateToURL(const std::string& text) override {
    if (text.empty()) {
      return;
    }
    GURL url(text);
    // A bare "example.com" has no scheme and parses as invalid; retry as https.
    if (!url.is_valid() || !url.has_scheme()) {
      url = GURL("https://" + text);
    }
    if (url.is_valid()) {
      shell_->LoadURL(url);
    }
  }

  // Add/show bookmarks live entirely in the shim's toolbar now (BookmarkStore
  // + BookmarksWindow), so the delegate only needs to navigate.

 private:
  raw_ptr<Shell> shell_;
};

// content_shell's own FillLayout sizes the WebContents windows to the host
// only once, at creation (the upstream shell is never resized by a user), so
// a BWindow resize would leave the page at its original size. Follow every
// host resize by refitting each child window to the host.
class HostResizeObserver : public aura::WindowTreeHostObserver {
 public:
  void OnHostResized(aura::WindowTreeHost* host) override {
    aura::Window* root = host->window();
    const gfx::Rect fill(root->bounds().size());
    for (aura::Window* child : root->children()) {
      child->SetBounds(fill);
    }
  }
};

void FocusContentsSoon(base::WeakPtr<WebContents> contents, int attempts_left);

// Focus the page, retrying on later turns of the loop while there is still
// nothing focusable. RenderWidgetHostViewAura::Focus() is a no-op until the
// view has a focus client and its window can take focus, and the view itself
// is created and shown asynchronously, so the first attempt -- made from
// SetContents -- routinely comes too early.
void FocusContentsNow(base::WeakPtr<WebContents> contents, int attempts_left) {
  WebContents* web_contents = contents.get();
  if (!web_contents) {
    return;
  }
  RenderWidgetHostView* view = web_contents->GetRenderWidgetHostView();
  if (view && view->HasFocus()) {
    return;
  }
  web_contents->Focus();
  view = web_contents->GetRenderWidgetHostView();
  if (view && view->HasFocus()) {
    return;
  }
  if (attempts_left <= 0) {
    LOG(ERROR) << "haiku: web contents never took focus; view=" << view;
    return;
  }
  FocusContentsSoon(std::move(contents), attempts_left - 1);
}

void FocusContentsSoon(base::WeakPtr<WebContents> contents, int attempts_left) {
  // Spread the retries over real time: what is being waited for is the view's
  // creation and the host window's Show(), and posting without a delay would
  // burn every attempt in the same millisecond.
  base::SequencedTaskRunner::GetCurrentDefault()->PostDelayedTask(
      FROM_HERE,
      base::BindOnce(&FocusContentsNow, std::move(contents), attempts_left),
      base::Milliseconds(50));
}

}  // namespace

struct ShellPlatformDelegate::ShellData {
  gfx::NativeWindow window = gfx::NativeWindow();
  gfx::AcceleratedWidget widget = gfx::kNullAcceleratedWidget;
  std::unique_ptr<ShellToolbarObserver> toolbar_observer;
  // Enabled state Shell reports one button at a time; the shim wants both.
  bool back_enabled = false;
  bool forward_enabled = false;
};

struct ShellPlatformDelegate::PlatformData {
  std::unique_ptr<ShellPlatformDataAura> aura;
  HostResizeObserver resize_observer;
};

ShellPlatformDelegate::ShellPlatformDelegate() = default;
ShellPlatformDelegate::~ShellPlatformDelegate() {
  if (platform_ && platform_->aura) {
    platform_->aura->host()->RemoveObserver(&platform_->resize_observer);
  }
}

void ShellPlatformDelegate::Initialize(const gfx::Size& default_window_size) {
  platform_ = std::make_unique<PlatformData>();
  platform_->aura =
      std::make_unique<ShellPlatformDataAura>(default_window_size);
  platform_->aura->host()->AddObserver(&platform_->resize_observer);
}

void ShellPlatformDelegate::CreatePlatformWindow(
    Shell* shell,
    const gfx::Size& initial_size) {
  DCHECK(!shell_data_map_.contains(shell));
  ShellData& shell_data = shell_data_map_[shell];

  // All shells share the one host window. Upstream resizes it with
  // ResizeWindow(), i.e. gfx::Rect(size) at (0,0): a new window opened from a
  // link would yank the BWindow back to the top-left corner, tab off screen.
  // Keep the origin where the user left it and only apply the size.
  aura::WindowTreeHost* host = platform_->aura->host();
  gfx::Rect bounds = host->GetBoundsInPixels();
  bounds.set_size(initial_size);
  host->SetBoundsInPixels(bounds);

  shell_data.window = host->window();
  shell_data.widget = host->GetAcceleratedWidget();
  shell_data.toolbar_observer = std::make_unique<ShellToolbarObserver>(shell);
  ui::SetHaikuToolbarObserver(shell_data.widget,
                              shell_data.toolbar_observer.get());
}

gfx::NativeWindow ShellPlatformDelegate::GetNativeWindow(Shell* shell) {
  DCHECK(shell_data_map_.contains(shell));
  return shell_data_map_[shell].window;
}

void ShellPlatformDelegate::CleanUp(Shell* shell) {
  DCHECK(shell_data_map_.contains(shell));
  ShellData& shell_data = shell_data_map_[shell];
  ui::SetHaikuToolbarObserver(shell_data.widget, nullptr);
  shell_data_map_.erase(shell);
}

void ShellPlatformDelegate::SetContents(Shell* shell) {
  aura::Window* content = shell->web_contents()->GetNativeView();
  aura::Window* parent = platform_->aura->host()->window();
  if (!parent->Contains(content)) {
    parent->AddChild(content);
  }
  content->Show();

  // The aura path never shows the host (native) window on its own -- unlike the
  // views delegate, which calls GetHost()->Show() explicitly. Without this the
  // BWindow stays hidden and only the desktop is visible.
  platform_->aura->ShowWindow();

  // Nothing focuses the contents in this configuration: the aura delegate is
  // upstream's web-test one, where focus arrives from the test runner, and the
  // only local focus client is the shell's own. Until the user clicked the
  // page, document.hasFocus() was false and every key was dropped -- the
  // click works because RenderWidgetHostViewEventHandler calls
  // SetKeyboardFocus() on mouse-down.
  //
  // Focusing right here is not enough: WebContentsViewAura::Focus() reaches
  // RenderWidgetHostViewAura::Focus(), which does nothing unless the view
  // already has a focus client and its window can take focus, and neither is
  // settled while SetContents is still running. Posting the focus makes it
  // run once the window tree, the host's Show() and the view's own Show()
  // have all been processed.
  FocusContentsSoon(shell->web_contents()->GetWeakPtr(), 30);
}

void ShellPlatformDelegate::ResizeWebContent(Shell* shell,
                                             const gfx::Size& content_size) {
  shell->web_contents()->GetRenderWidgetHostView()->SetSize(content_size);
}

void ShellPlatformDelegate::EnableUIControl(Shell* shell,
                                            UIControl control,
                                            bool is_enabled) {
  auto it = shell_data_map_.find(shell);
  if (it == shell_data_map_.end()) {
    return;
  }
  ShellData& shell_data = it->second;
  if (control == BACK_BUTTON) {
    shell_data.back_enabled = is_enabled;
  } else if (control == FORWARD_BUTTON) {
    shell_data.forward_enabled = is_enabled;
  } else {
    // STOP_BUTTON is driven by SetIsLoading instead.
    return;
  }
  ui::HaikuToolbarSetNavigationEnabled(
      shell_data.widget, shell_data.back_enabled, shell_data.forward_enabled);
}

void ShellPlatformDelegate::SetAddressBarURL(Shell* shell, const GURL& url) {
  auto it = shell_data_map_.find(shell);
  if (it != shell_data_map_.end()) {
    ui::HaikuToolbarSetAddress(it->second.widget, url.spec());
  }
}

void ShellPlatformDelegate::SetIsLoading(Shell* shell, bool loading) {
  auto it = shell_data_map_.find(shell);
  if (it != shell_data_map_.end()) {
    ui::HaikuToolbarSetLoading(it->second.widget, loading);
  }
}

void ShellPlatformDelegate::SetTitle(Shell* shell,
                                     const std::u16string& title) {
  auto it = shell_data_map_.find(shell);
  if (it != shell_data_map_.end()) {
    ui::HaikuToolbarSetTitle(it->second.widget, base::UTF16ToUTF8(title));
  }
}

void ShellPlatformDelegate::MainFrameCreated(Shell* shell,
                                             RenderFrameHost* main_frame) {}

bool ShellPlatformDelegate::DestroyShell(Shell* shell) {
  return false;  // Shell destroys itself.
}

}  // namespace content
