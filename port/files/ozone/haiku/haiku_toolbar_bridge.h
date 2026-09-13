// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef UI_OZONE_PLATFORM_HAIKU_HAIKU_TOOLBAR_BRIDGE_H_
#define UI_OZONE_PLATFORM_HAIKU_HAIKU_TOOLBAR_BRIDGE_H_

#include <string>

#include "ui/gfx/native_ui_types.h"

// The narrow seam between content_shell's Haiku delegate and the ozone Haiku
// window, so the delegate never has to include an ozone platform-internal
// header. Everything here is addressed by AcceleratedWidget and is
// UI-thread-only: the window posts toolbar events to the UI thread before
// calling an observer, and the delegate pushes state from the UI thread.

namespace ui {

// Implemented by content_shell's delegate; called when the user drives the
// native toolbar. On the UI thread.
class HaikuToolbarObserver {
 public:
  virtual void OnNavigateBack() = 0;
  virtual void OnNavigateForward() = 0;
  virtual void OnReloadOrStop() = 0;
  virtual void OnNavigateToURL(const std::string& text) = 0;

 protected:
  ~HaikuToolbarObserver() = default;
};

// Register/clear the observer for a window. The delegate calls these in
// CreatePlatformWindow / CleanUp.
void SetHaikuToolbarObserver(gfx::AcceleratedWidget widget,
                             HaikuToolbarObserver* observer);

// State pushed from the delegate into the toolbar. No-ops if the widget has no
// window or the window has no toolbar.
void HaikuToolbarSetAddress(gfx::AcceleratedWidget widget,
                            const std::string& url);
void HaikuToolbarSetLoading(gfx::AcceleratedWidget widget, bool loading);
void HaikuToolbarSetNavigationEnabled(gfx::AcceleratedWidget widget,
                                      bool back,
                                      bool forward);
void HaikuToolbarSetTitle(gfx::AcceleratedWidget widget,
                          const std::string& title);

// Called by HaikuWindow (on the UI thread) to reach the registered observer.
// Returns null if none is registered for the widget.
HaikuToolbarObserver* GetHaikuToolbarObserver(gfx::AcceleratedWidget widget);

}  // namespace ui

#endif  // UI_OZONE_PLATFORM_HAIKU_HAIKU_TOOLBAR_BRIDGE_H_
