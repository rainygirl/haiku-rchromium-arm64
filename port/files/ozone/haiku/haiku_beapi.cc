// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "ui/ozone/platform/haiku/haiku_beapi.h"

// The BeAPI constants the translation below names: modifier keys and
// B_*_MOUSE_BUTTON from InterfaceDefs.h, B_ENTERED_VIEW and
// B_EXITED_VIEW from View.h. Nothing here derives from a BeAPI class;
// see haiku_shim.h.
#include <InterfaceDefs.h>
#include <View.h>

#include <memory>
#include <utility>

#include "base/functional/bind.h"
#include "base/task/single_thread_task_runner.h"
#include "ui/events/base_event_utils.h"
#include "ui/events/event.h"
#include "ui/events/keycodes/keyboard_codes_posix.h"
#include "ui/ozone/platform/haiku/haiku_window.h"

namespace ui {

namespace {

int EventFlagsFromModifiers(unsigned int mods) {
  int flags = EF_NONE;
  if (mods & B_SHIFT_KEY) {
    flags |= EF_SHIFT_DOWN;
  }
  if (mods & B_CONTROL_KEY) {
    flags |= EF_CONTROL_DOWN;
  }
  // Haiku's Command key sits where Alt does on a PC keyboard and is what
  // users press for shortcuts, so it maps to Control's role in Chromium
  // only on menus; here it stays Alt, matching what the key produces.
  if (mods & B_COMMAND_KEY) {
    flags |= EF_ALT_DOWN;
  }
  if (mods & B_OPTION_KEY) {
    flags |= EF_ALTGR_DOWN;
  }
  if (mods & B_CAPS_LOCK) {
    flags |= EF_CAPS_LOCK_ON;
  }
  return flags;
}

int EventFlagsFromButtons(int buttons) {
  int flags = EF_NONE;
  if (buttons & B_PRIMARY_MOUSE_BUTTON) {
    flags |= EF_LEFT_MOUSE_BUTTON;
  }
  if (buttons & B_SECONDARY_MOUSE_BUTTON) {
    flags |= EF_RIGHT_MOUSE_BUTTON;
  }
  if (buttons & B_TERTIARY_MOUSE_BUTTON) {
    flags |= EF_MIDDLE_MOUSE_BUTTON;
  }
  return flags;
}

// Maps the B_* named keys Haiku reports in bytes[0] onto Chromium key codes.
KeyboardCode KeyboardCodeFromByte(char c) {
  switch (c) {
    case B_BACKSPACE:
      return VKEY_BACK;
    case B_RETURN:
      return VKEY_RETURN;
    case B_TAB:
      return VKEY_TAB;
    case B_ESCAPE:
      return VKEY_ESCAPE;
    case B_SPACE:
      return VKEY_SPACE;
    case B_LEFT_ARROW:
      return VKEY_LEFT;
    case B_RIGHT_ARROW:
      return VKEY_RIGHT;
    case B_UP_ARROW:
      return VKEY_UP;
    case B_DOWN_ARROW:
      return VKEY_DOWN;
    case B_INSERT:
      return VKEY_INSERT;
    case B_DELETE:
      return VKEY_DELETE;
    case B_HOME:
      return VKEY_HOME;
    case B_END:
      return VKEY_END;
    case B_PAGE_UP:
      return VKEY_PRIOR;
    case B_PAGE_DOWN:
      return VKEY_NEXT;
    default:
      break;
  }
  if (c >= 'a' && c <= 'z') {
    return static_cast<KeyboardCode>(VKEY_A + (c - 'a'));
  }
  if (c >= 'A' && c <= 'Z') {
    return static_cast<KeyboardCode>(VKEY_A + (c - 'A'));
  }
  if (c >= '0' && c <= '9') {
    return static_cast<KeyboardCode>(VKEY_0 + (c - '0'));
  }
  return VKEY_UNKNOWN;
}

}  // namespace

HaikuEventBridge::HaikuEventBridge(
    base::WeakPtr<HaikuWindow> window,
    scoped_refptr<base::SingleThreadTaskRunner> ui_task_runner)
    : window_(std::move(window)),
      ui_task_runner_(std::move(ui_task_runner)) {}

HaikuEventBridge::~HaikuEventBridge() = default;

void HaikuEventBridge::OnMouseDown(float x,
                                   float y,
                                   unsigned int modifiers,
                                   int buttons,
                                   int clicks) {
  int flags =
      EventFlagsFromModifiers(modifiers) | EventFlagsFromButtons(buttons);
  if (clicks == 2) {
    flags |= EF_IS_DOUBLE_CLICK;
  }
  gfx::PointF location(x, y);
  auto event = std::make_unique<MouseEvent>(EventType::kMousePressed, location,
                                            location, EventTimeForNow(), flags,
                                            flags);
  ui_task_runner_->PostTask(
      FROM_HERE, base::BindOnce(&HaikuWindow::OnEventFromWindowThread, window_,
                                std::move(event)));
}

void HaikuEventBridge::OnMouseUp(float x,
                                 float y,
                                 unsigned int modifiers,
                                 int buttons) {
  // On release Haiku reports the buttons still held, which is empty for a
  // simple click, so name the button from what the message carried.
  int changed = EventFlagsFromButtons(buttons);
  if (changed == EF_NONE) {
    changed = EF_LEFT_MOUSE_BUTTON;
  }
  const int flags = EventFlagsFromModifiers(modifiers) | changed;
  gfx::PointF location(x, y);
  auto event = std::make_unique<MouseEvent>(EventType::kMouseReleased, location,
                                            location, EventTimeForNow(), flags,
                                            changed);
  ui_task_runner_->PostTask(
      FROM_HERE, base::BindOnce(&HaikuWindow::OnEventFromWindowThread, window_,
                                std::move(event)));
}

void HaikuEventBridge::OnMouseMoved(float x,
                                    float y,
                                    unsigned int modifiers,
                                    int buttons,
                                    unsigned int transit) {
  const int flags =
      EventFlagsFromModifiers(modifiers) | EventFlagsFromButtons(buttons);
  EventType type =
      buttons ? EventType::kMouseDragged : EventType::kMouseMoved;
  if (transit == B_EXITED_VIEW) {
    type = EventType::kMouseExited;
  } else if (transit == B_ENTERED_VIEW) {
    type = EventType::kMouseEntered;
  }
  gfx::PointF location(x, y);
  auto event = std::make_unique<MouseEvent>(type, location, location,
                                            EventTimeForNow(), flags, EF_NONE);
  ui_task_runner_->PostTask(
      FROM_HERE, base::BindOnce(&HaikuWindow::OnEventFromWindowThread, window_,
                                std::move(event)));
}

void HaikuEventBridge::OnKey(bool pressed,
                             const char* bytes,
                             int num_bytes,
                             unsigned int modifiers) {
  if (num_bytes < 1) {
    return;
  }
  const int flags = EventFlagsFromModifiers(modifiers);
  const KeyboardCode code = KeyboardCodeFromByte(bytes[0]);
  auto event = std::make_unique<KeyEvent>(
      pressed ? EventType::kKeyPressed : EventType::kKeyReleased, code, flags);
  ui_task_runner_->PostTask(
      FROM_HERE, base::BindOnce(&HaikuWindow::OnEventFromWindowThread, window_,
                                std::move(event)));
}

void HaikuEventBridge::OnViewResized(float width, float height) {
  // BView::FrameResized hands over the new width/height in Be's inclusive
  // pixel convention; the origin is unknown here and stays what it was.
  gfx::Size size(static_cast<int>(width) + 1, static_cast<int>(height) + 1);
  ui_task_runner_->PostTask(
      FROM_HERE, base::BindOnce(&HaikuWindow::OnSizeChangedFromWindowThread,
                                window_, size));
}

void HaikuEventBridge::OnQuitRequested() {
  ui_task_runner_->PostTask(
      FROM_HERE, base::BindOnce(&HaikuWindow::OnCloseRequestedFromWindowThread,
                                window_));
}

void HaikuEventBridge::OnActivated(bool active) {
  ui_task_runner_->PostTask(
      FROM_HERE,
      base::BindOnce(&HaikuWindow::OnActivationChangedFromWindowThread, window_,
                     active));
}

void HaikuEventBridge::OnFrameMoved(float x,
                                    float y,
                                    float width,
                                    float height) {
  gfx::Rect bounds(static_cast<int>(x), static_cast<int>(y),
                   static_cast<int>(width), static_cast<int>(height));
  ui_task_runner_->PostTask(
      FROM_HERE, base::BindOnce(&HaikuWindow::OnBoundsChangedFromWindowThread,
                                window_, bounds));
}

void HaikuEventBridge::OnNavigateBack() {
  ui_task_runner_->PostTask(
      FROM_HERE, base::BindOnce(&HaikuWindow::OnToolbarBack, window_));
}

void HaikuEventBridge::OnNavigateForward() {
  ui_task_runner_->PostTask(
      FROM_HERE, base::BindOnce(&HaikuWindow::OnToolbarForward, window_));
}

void HaikuEventBridge::OnReloadOrStop() {
  ui_task_runner_->PostTask(
      FROM_HERE, base::BindOnce(&HaikuWindow::OnToolbarReloadOrStop, window_));
}

void HaikuEventBridge::OnNavigateToURL(const char* utf8) {
  // The pointer is only valid during this call, so copy before posting.
  std::string text(utf8 != nullptr ? utf8 : "");
  ui_task_runner_->PostTask(
      FROM_HERE, base::BindOnce(&HaikuWindow::OnToolbarNavigateToURL, window_,
                                std::move(text)));
}

}  // namespace ui
