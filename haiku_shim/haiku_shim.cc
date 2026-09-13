// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Built with the same gcc that built libbe, not with Chromium's clang. See
// haiku_shim.h for why the BeAPI subclasses cannot live inside Chromium.

#include "haiku_shim.h"

#include <Application.h>
#include <Bitmap.h>
#include <Message.h>
#include <OS.h>
#include <Rect.h>
#include <Screen.h>
#include <View.h>
#include <Window.h>
#include <Button.h>
#include <TextControl.h>
#include <InterfaceDefs.h>

namespace haiku_shim {

namespace {

// The signature app_server files this team under. It has to be a valid MIME
// type or BApplication refuses to construct.
const char kAppSignature[] = "application/x-vnd.Chromium-Ozone";

// The R Chromium native toolbar. Height in pixels of the strip above the web
// content, and the BMessage `what` codes the controls post to the window.
const float kToolbarHeight = 32.0f;
enum {
  kMsgBack = 'back',
  kMsgForward = 'fwrd',
  kMsgReloadOrStop = 'rlod',
  kMsgGo = 'entr',
};

sem_id g_app_ready = -1;
bool g_app_started = false;

int32 AppThreadEntry(void*) {
  // Stack-allocated and never destroyed: Run() only returns when the
  // application quits, which for this process means the whole team is going
  // away anyway.
  BApplication app(kAppSignature);
  // The constructor above sets be_app, so windows can be built from this
  // point on; callers do not have to wait for Run() to reach its loop.
  release_sem(g_app_ready);
  app.Run();
  return 0;
}

class ShimView : public BView {
 public:
  ShimView(BRect frame, Delegate* delegate)
      : BView(frame,
              "ChromiumView",
              B_FOLLOW_ALL_SIDES,
              B_WILL_DRAW | B_FRAME_EVENTS | B_NAVIGABLE),
        delegate_(delegate) {
    SetViewColor(B_TRANSPARENT_COLOR);
  }

  ~ShimView() { delete bitmap_; }

  // Takes ownership of a copy of the pixels so Draw() can repaint without
  // asking the compositor for another frame.
  void SetFrontBuffer(BBitmap* bitmap) {
    delete bitmap_;
    bitmap_ = bitmap;
  }

  void Draw(BRect update) {
    if (bitmap_ != NULL) {
      DrawBitmap(bitmap_, update, update);
    }
  }

  void MouseDown(BPoint where) {
    int32 buttons = 0;
    int32 clicks = 1;
    BMessage* msg = BView::Window()->CurrentMessage();
    if (msg != NULL) {
      msg->FindInt32("buttons", &buttons);
      msg->FindInt32("clicks", &clicks);
    }
    delegate_->OnMouseDown(where.x, where.y, modifiers(), buttons, clicks);
  }

  void MouseUp(BPoint where) {
    int32 buttons = 0;
    BMessage* msg = BView::Window()->CurrentMessage();
    if (msg != NULL) {
      msg->FindInt32("buttons", &buttons);
    }
    delegate_->OnMouseUp(where.x, where.y, modifiers(), buttons);
  }

  void MouseMoved(BPoint where, uint32 transit, const BMessage*) {
    int32 buttons = 0;
    BMessage* msg = BView::Window()->CurrentMessage();
    if (msg != NULL) {
      msg->FindInt32("buttons", &buttons);
    }
    delegate_->OnMouseMoved(where.x, where.y, modifiers(), buttons, transit);
  }

  void KeyDown(const char* bytes, int32 numBytes) {
    delegate_->OnKey(true, bytes, numBytes, modifiers());
  }

  void KeyUp(const char* bytes, int32 numBytes) {
    delegate_->OnKey(false, bytes, numBytes, modifiers());
  }

  void FrameResized(float width, float height) {
    delegate_->OnViewResized(width, height);
  }

 private:
  Delegate* delegate_;
  BBitmap* bitmap_;
};

class ShimWindow : public BWindow, public NativeWindow {
 public:
  ShimWindow(BRect frame, bool has_frame, bool with_toolbar, Delegate* delegate)
      // Borderless is a window_look, not a window_type: the window_type enum
      // has no undecorated member, so this takes the look/feel constructor
      // and names the decoration directly.
      : BWindow(frame,
                "Chromium",
                has_frame ? B_TITLED_WINDOW_LOOK : B_NO_BORDER_WINDOW_LOOK,
                B_NORMAL_WINDOW_FEEL,
                B_ASYNCHRONOUS_CONTROLS),
        delegate_(delegate),
        with_toolbar_(with_toolbar) {
    BRect content = Bounds();
    if (with_toolbar_) {
      content.top = kToolbarHeight;
      BuildToolbar(Bounds().Width());
    }
    view_ = new ShimView(content, delegate);
    AddChild(view_);
    // BWindow's constructor leaves the looper locked and does not start its
    // thread; Show() is what normally calls Run(). Do it here instead,
    // because Run() asserts the looper is locked and Show() unlocks before
    // it gets there -- a window that was merely Unlock()ed after
    // construction kills the team with "looper must be locked before
    // proceeding" the first time anything tries to show it. Run() spawns the
    // window thread and drops the constructor's lock itself.
    Run();
  }

  // BWindow. QuitRequested runs on the window thread and must not tear the
  // window down on its own: Chromium decides that, so this only reports the
  // request and refuses the quit.
  bool QuitRequested() {
    delegate_->OnQuitRequested();
    return false;
  }

  void WindowActivated(bool active) { delegate_->OnActivated(active); }

  void FrameMoved(BPoint origin) {
    BRect f = Frame();
    delegate_->OnFrameMoved(origin.x, origin.y, f.Width() + 1, f.Height() + 1);
  }

  // The controls post plain BMessages to the window; MessageReceived turns
  // them into delegate calls, on the window thread like every other callback.
  void MessageReceived(BMessage* what) {
    switch (what->what) {
      case kMsgBack:
        delegate_->OnNavigateBack();
        break;
      case kMsgForward:
        delegate_->OnNavigateForward();
        break;
      case kMsgReloadOrStop:
        delegate_->OnReloadOrStop();
        break;
      case kMsgGo:
        delegate_->OnNavigateToURL(address_ != NULL ? address_->Text() : "");
        break;
      default:
        BWindow::MessageReceived(what);
    }
  }

  // NativeWindow:
  void ShowWindow(bool inactive) {
    if (!LockLooper()) {
      return;
    }
    BWindow::Show();
    if (inactive) {
      BWindow::Activate(false);
    }
    UnlockLooper();
  }

  void HideWindow() {
    if (!LockLooper()) {
      return;
    }
    BWindow::Hide();
    UnlockLooper();
  }

  void SetWindowBounds(float x, float y, float width, float height) {
    if (!LockLooper()) {
      return;
    }
    MoveTo(x, y);
    ResizeTo(width - 1, height - 1);
    UnlockLooper();
  }

  void GetWindowFrame(float out_xywh[4]) {
    out_xywh[0] = out_xywh[1] = out_xywh[2] = out_xywh[3] = 0;
    if (!LockLooper()) {
      return;
    }
    BRect f = Frame();
    out_xywh[0] = f.left;
    out_xywh[1] = f.top;
    out_xywh[2] = f.Width() + 1;
    out_xywh[3] = f.Height() + 1;
    UnlockLooper();
  }

  void SetWindowTitle(const char* utf8) {
    if (!LockLooper()) {
      return;
    }
    BWindow::SetTitle(utf8);
    UnlockLooper();
  }

  void ZoomWindow() {
    if (!LockLooper()) {
      return;
    }
    BWindow::Zoom();
    UnlockLooper();
  }

  void MinimizeWindow(bool minimize) {
    if (!LockLooper()) {
      return;
    }
    BWindow::Minimize(minimize);
    UnlockLooper();
  }

  void ActivateWindow(bool active) {
    if (!LockLooper()) {
      return;
    }
    BWindow::Activate(active);
    UnlockLooper();
  }

  void PresentBitmap(BBitmap* bitmap, float x, float y, float width, float height) {
    if (!LockLooper()) {
      delete bitmap;
      return;
    }
    view_->SetFrontBuffer(bitmap);
    view_->Invalidate(BRect(x, y, x + width - 1, y + height - 1));
    UnlockLooper();
  }

  void SetAddressText(const char* utf8) {
    if (!with_toolbar_ || address_ == NULL) {
      return;
    }
    if (!LockLooper()) {
      return;
    }
    address_->SetText(utf8 != NULL ? utf8 : "");
    UnlockLooper();
  }

  void SetLoadingState(bool loading) {
    loading_ = loading;
    if (!with_toolbar_ || reload_ == NULL) {
      return;
    }
    if (!LockLooper()) {
      return;
    }
    // Icon-only art comes later; for now the label carries Reload vs Stop.
    reload_->SetLabel(loading ? "x" : "R");
    UnlockLooper();
  }

  void SetNavigationEnabled(bool back, bool forward) {
    if (!with_toolbar_) {
      return;
    }
    if (!LockLooper()) {
      return;
    }
    if (back_ != NULL) {
      back_->SetEnabled(back);
    }
    if (forward_ != NULL) {
      forward_->SetEnabled(forward);
    }
    UnlockLooper();
  }

  void DestroyWindow() {
    // Quit() deletes the BWindow, and with it the view and this object.
    if (LockLooper()) {
      BWindow::Quit();
    }
  }

 private:
  // Runs in the constructor, before the window thread starts, so no lock.
  void BuildToolbar(float width) {
    toolbar_ = new BView(BRect(0, 0, width, kToolbarHeight - 1),
                         "toolbar",
                         B_FOLLOW_LEFT_RIGHT | B_FOLLOW_TOP,
                         B_WILL_DRAW);
    AddChild(toolbar_);

    float x = 4;
    const float bw = 30;
    const float bh = kToolbarHeight - 6;
    back_ = new BButton(BRect(x, 3, x + bw, 3 + bh), "back", "<",
                        new BMessage(kMsgBack));
    x += bw + 4;
    forward_ = new BButton(BRect(x, 3, x + bw, 3 + bh), "forward", ">",
                           new BMessage(kMsgForward));
    x += bw + 4;
    reload_ = new BButton(BRect(x, 3, x + bw, 3 + bh), "reload", "R",
                          new BMessage(kMsgReloadOrStop));
    x += bw + 8;
    address_ = new BTextControl(BRect(x, 4, width - 8, 3 + bh), "address", NULL,
                                "", new BMessage(kMsgGo));
    address_->SetDivider(0);
    address_->SetResizingMode(B_FOLLOW_LEFT_RIGHT | B_FOLLOW_TOP);

    toolbar_->AddChild(back_);
    toolbar_->AddChild(forward_);
    toolbar_->AddChild(reload_);
    toolbar_->AddChild(address_);

    // Deliver the controls' messages to this window, whatever thread built it.
    back_->SetTarget(this);
    forward_->SetTarget(this);
    reload_->SetTarget(this);
    address_->SetTarget(this);
  }

  Delegate* delegate_;
  ShimView* view_;
  bool with_toolbar_ = false;
  bool loading_ = false;
  BView* toolbar_ = NULL;
  BButton* back_ = NULL;
  BButton* forward_ = NULL;
  BButton* reload_ = NULL;
  BTextControl* address_ = NULL;
};

}  // namespace

extern "C" void HaikuShimEnsureApp() {
  if (g_app_started) {
    return;
  }
  g_app_started = true;

  // Haiku's own semaphore rather than a Chromium primitive: this runs during
  // InitializeUI on the UI thread, where Chromium's thread restrictions
  // disallow blocking on a sync primitive. acquire_sem is the platform's
  // primitive and is what BeAPI code would use here in any case.
  g_app_ready = create_sem(0, "haiku app ready");
  if (g_app_ready < B_OK) {
    return;
  }

  thread_id thread =
      spawn_thread(AppThreadEntry, "HaikuApp", B_NORMAL_PRIORITY, NULL);
  if (thread < B_OK) {
    delete_sem(g_app_ready);
    g_app_ready = -1;
    return;
  }
  resume_thread(thread);

  // Restart on interruption so a signal during startup does not let the
  // caller proceed without be_app.
  status_t status;
  do {
    status = acquire_sem(g_app_ready);
  } while (status == B_INTERRUPTED);
}

extern "C" NativeWindow* HaikuShimCreateWindow(float x,
                                         float y,
                                         float width,
                                         float height,
                                         bool has_frame,
                                         bool with_toolbar,
                                               Delegate* delegate) {
  BRect frame(x, y, x + width - 1, y + height - 1);
  return new ShimWindow(frame, has_frame, with_toolbar, delegate);
}

extern "C" void HaikuShimScreenFrame(float out_xywh[4]) {
  BScreen screen(B_MAIN_SCREEN_ID);
  BRect f = screen.Frame();
  out_xywh[0] = f.left;
  out_xywh[1] = f.top;
  out_xywh[2] = f.Width() + 1;
  out_xywh[3] = f.Height() + 1;
}

}  // namespace haiku_shim
