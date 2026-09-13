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

#include "base/base_paths.h"
#include "base/files/file_path.h"
#include "base/files/file_util.h"
#include "base/memory/raw_ptr.h"
#include "base/path_service.h"
#include "base/strings/stringprintf.h"
#include "base/strings/string_split.h"
#include "base/strings/utf_string_conversions.h"
#include "base/time/time.h"
#include "content/public/browser/render_widget_host_view.h"
#include "content/public/browser/web_contents.h"
#include "content/shell/browser/shell.h"
#include "content/shell/browser/shell_platform_data_aura.h"
#include "ui/aura/env.h"
#include "ui/aura/window.h"
#include "ui/aura/window_event_dispatcher.h"
#include "ui/aura/window_tree_host.h"
#include "ui/ozone/platform/haiku/haiku_toolbar_bridge.h"
#include "url/gurl.h"

namespace content {

namespace {

// One per Shell. Receives toolbar events (on the UI thread, posted by the
// ozone bridge) and turns them into Shell navigation.
class ShellToolbarObserver final : public ui::HaikuToolbarObserver {
 public:
  ShellToolbarObserver(Shell* shell, gfx::AcceleratedWidget widget)
      : shell_(shell), widget_(widget) {}

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

  void OnAddBookmark() override {
    if (!shell_->web_contents())
      return;
    const GURL url = shell_->web_contents()->GetLastCommittedURL();
    if (!url.is_valid())
      return;
    std::string title = base::UTF16ToUTF8(shell_->web_contents()->GetTitle());
    // The store is one tab-separated line per entry, so strip separators.
    for (char& c : title)
      if (c == '\t' || c == '\n' || c == '\r')
        c = ' ';

    base::Time::Exploded now;
    base::Time::Now().LocalExplode(&now);
    std::string line = base::StringPrintf("%s\t%s\t%04d-%02d-%02d\n",
                                          url.spec().c_str(), title.c_str(),
                                          now.year, now.month, now.day_of_month);
    base::FilePath path = BookmarksPath();
    if (!path.empty())
      base::AppendToFile(path, line);
  }

  void OnShowBookmarks() override {
    std::string data;
    base::FilePath path = BookmarksPath();
    if (!path.empty())
      base::ReadFileToString(path, &data);
    // Newest first: reverse the stored (append-order) lines.
    std::vector<std::string> lines = base::SplitString(
        data, "\n", base::TRIM_WHITESPACE, base::SPLIT_WANT_NONEMPTY);
    std::string tsv;
    for (auto it = lines.rbegin(); it != lines.rend(); ++it) {
      if (!it->empty())
        tsv += *it + "\n";
    }
    ui::HaikuToolbarShowBookmarks(widget_, tsv);
  }

 private:
  static base::FilePath BookmarksPath() {
    base::FilePath home;
    if (!base::PathService::Get(base::DIR_HOME, &home))
      return base::FilePath();
    return home.Append(".rchromium-bookmarks.tsv");
  }

  raw_ptr<Shell> shell_;
  gfx::AcceleratedWidget widget_;
};

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
};

ShellPlatformDelegate::ShellPlatformDelegate() = default;
ShellPlatformDelegate::~ShellPlatformDelegate() = default;

void ShellPlatformDelegate::Initialize(const gfx::Size& default_window_size) {
  platform_ = std::make_unique<PlatformData>();
  platform_->aura =
      std::make_unique<ShellPlatformDataAura>(default_window_size);
}

void ShellPlatformDelegate::CreatePlatformWindow(
    Shell* shell,
    const gfx::Size& initial_size) {
  DCHECK(!shell_data_map_.contains(shell));
  ShellData& shell_data = shell_data_map_[shell];

  platform_->aura->ResizeWindow(initial_size);

  aura::WindowTreeHost* host = platform_->aura->host();
  shell_data.window = host->window();
  shell_data.widget = host->GetAcceleratedWidget();
  shell_data.toolbar_observer =
      std::make_unique<ShellToolbarObserver>(shell, shell_data.widget);
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
                                     const std::u16string& title) {}

void ShellPlatformDelegate::MainFrameCreated(Shell* shell,
                                             RenderFrameHost* main_frame) {}

bool ShellPlatformDelegate::DestroyShell(Shell* shell) {
  return false;  // Shell destroys itself.
}

}  // namespace content
