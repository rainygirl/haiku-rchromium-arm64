// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef UI_OZONE_PLATFORM_HAIKU_HAIKU_WINDOW_H_
#define UI_OZONE_PLATFORM_HAIKU_HAIKU_WINDOW_H_

#include <memory>
#include <optional>
#include <string>

#include "base/memory/raw_ptr.h"
#include "base/memory/scoped_refptr.h"
#include "base/memory/weak_ptr.h"
#include "base/task/single_thread_task_runner.h"
#include "ui/events/event.h"
#include "ui/gfx/geometry/rect.h"
#include "ui/gfx/native_ui_types.h"
#include "ui/platform_window/platform_window.h"
#include "ui/platform_window/platform_window_delegate.h"

#include "ui/ozone/platform/haiku/haiku_beapi.h"

class BBitmap;

namespace ui {

class HaikuWindowManager;

// A PlatformWindow backed by a real BWindow.
//
// Threading is the whole story here. Haiku gives every BWindow its own
// thread, and BView hooks (Draw, MouseDown, KeyDown) run on that thread --
// never on Chromium's UI thread. So the view forwards input by posting to
// the task runner captured when the window was built, and everything that
// touches Chromium state stays on the UI thread. In the other direction,
// calls into the BWindow from Chromium threads take the window's lock.
class HaikuWindow : public PlatformWindow {
 public:
  HaikuWindow(PlatformWindowDelegate* delegate,
              HaikuWindowManager* manager,
              const gfx::Rect& bounds,
              bool has_frame);

  HaikuWindow(const HaikuWindow&) = delete;
  HaikuWindow& operator=(const HaikuWindow&) = delete;

  ~HaikuWindow() override;

  // PlatformWindow:
  void Show(bool inactive) override;
  void Hide() override;
  void Close() override;
  bool IsVisible() const override;
  void PrepareForShutdown() override;
  void SetBoundsInPixels(const gfx::Rect& bounds) override;
  gfx::Rect GetBoundsInPixels() const override;
  void SetBoundsInDIP(const gfx::Rect& bounds) override;
  gfx::Rect GetBoundsInDIP() const override;
  void SetTitle(const std::u16string& title) override;
  void SetCapture() override;
  void ReleaseCapture() override;
  bool HasCapture() const override;
  void SetFullscreen(bool fullscreen, int64_t target_display_id) override;
  void Maximize() override;
  void Minimize() override;
  void Restore() override;
  PlatformWindowState GetPlatformWindowState() const override;
  void Activate() override;
  void Deactivate() override;
  void SetUseNativeFrame(bool use_native_frame) override;
  bool ShouldUseNativeFrame() const override;
  void SetCursor(scoped_refptr<PlatformCursor> cursor) override;
  void MoveCursorTo(const gfx::Point& location) override;
  void ConfineCursorToBounds(const gfx::Rect& bounds) override;
  void SetRestoredBoundsInDIP(const gfx::Rect& bounds) override;
  gfx::Rect GetRestoredBoundsInDIP() const override;
  void SetWindowIcons(const gfx::ImageSkia& window_icon,
                      const gfx::ImageSkia& app_icon) override;
  void SizeConstraintsChanged() override;

  gfx::AcceleratedWidget widget() const { return widget_; }

  // Draws `bitmap` into the view. Called from the compositor thread by the
  // surface; takes the window lock itself.
  void PresentBitmap(BBitmap* bitmap, const gfx::Rect& damage);

  // Called on the UI thread, posted from the window thread.
  void OnEventFromWindowThread(std::unique_ptr<Event> event);
  void OnBoundsChangedFromWindowThread(const gfx::Rect& bounds);
  void OnCloseRequestedFromWindowThread();
  void OnActivationChangedFromWindowThread(bool active);

  // R Chromium native toolbar. The first group runs on the UI thread
  // (posted by the bridge) and drives navigation through the registered
  // HaikuToolbarObserver; the second is called from the delegate on the
  // UI thread and pushes state down into the shim toolbar.
  void OnToolbarBack();
  void OnToolbarForward();
  void OnToolbarReloadOrStop();
  void OnToolbarNavigateToURL(std::string text);
  void SetToolbarAddress(const std::string& url);
  void SetToolbarTitle(const std::string& title);
  void SetToolbarLoading(bool loading);
  void SetToolbarNavigationEnabled(bool back, bool forward);

  base::WeakPtr<HaikuWindow> GetWeakPtr() {
    return weak_ptr_factory_.GetWeakPtr();
  }

  scoped_refptr<base::SingleThreadTaskRunner> ui_task_runner() const {
    return ui_task_runner_;
  }

 private:
  void UpdateWindowState(PlatformWindowState new_state);

  raw_ptr<PlatformWindowDelegate> delegate_;
  raw_ptr<HaikuWindowManager> manager_;
  gfx::Rect bounds_;
  gfx::AcceleratedWidget widget_;

  // The bridge has to outlive the native window, which calls into it from
  // its own thread, so it is declared first and destroyed last.
  std::unique_ptr<HaikuEventBridge> bridge_;

  // Owned by the shim: DestroyWindow() quits the BWindow thread, which
  // deletes both. Raw, and cleared in the destructor.
  raw_ptr<haiku_shim::NativeWindow> window_ = nullptr;

  scoped_refptr<base::SingleThreadTaskRunner> ui_task_runner_;

  bool visible_ = false;
  bool has_capture_ = false;
  std::optional<gfx::Rect> restored_bounds_;
  PlatformWindowState window_state_ = PlatformWindowState::kUnknown;

  base::WeakPtrFactory<HaikuWindow> weak_ptr_factory_{this};
};

}  // namespace ui

#endif  // UI_OZONE_PLATFORM_HAIKU_HAIKU_WINDOW_H_
