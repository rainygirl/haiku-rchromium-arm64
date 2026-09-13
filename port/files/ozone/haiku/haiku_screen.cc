// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "ui/ozone/platform/haiku/haiku_screen.h"

#include <InterfaceDefs.h>
#include <Screen.h>

#include "ui/display/display.h"
#include "ui/gfx/geometry/point.h"
#include "ui/gfx/geometry/rect.h"
#include "ui/ozone/platform/haiku/haiku_window_manager.h"

namespace ui {

namespace {

constexpr int64_t kHaikuDisplayId = 1;

}  // namespace

HaikuScreen::HaikuScreen(HaikuWindowManager* window_manager)
    : window_manager_(window_manager) {
  BScreen screen(B_MAIN_SCREEN_ID);
  BRect frame = screen.Frame();
  gfx::Rect bounds(0, 0, static_cast<int>(frame.Width()) + 1,
                   static_cast<int>(frame.Height()) + 1);

  display::Display display(kHaikuDisplayId, bounds);
  display.set_device_scale_factor(1.0f);
  display_list_.AddDisplay(display, display::DisplayList::Type::PRIMARY);
}

HaikuScreen::~HaikuScreen() = default;

const std::vector<display::Display>& HaikuScreen::GetAllDisplays() const {
  return display_list_.displays();
}

display::Display HaikuScreen::GetPrimaryDisplay() const {
  auto it = display_list_.GetPrimaryDisplayIterator();
  CHECK(it != display_list_.displays().end());
  return *it;
}

display::Display HaikuScreen::GetDisplayForAcceleratedWidget(
    gfx::AcceleratedWidget widget) const {
  return GetPrimaryDisplay();
}

gfx::Point HaikuScreen::GetCursorScreenPoint() const {
  // get_mouse() reports in screen coordinates, which is what this returns.
  BPoint location;
  uint32 buttons = 0;
  get_mouse(&location, &buttons);
  return gfx::Point(static_cast<int>(location.x), static_cast<int>(location.y));
}

gfx::AcceleratedWidget HaikuScreen::GetAcceleratedWidgetAtScreenPoint(
    const gfx::Point& point) const {
  return window_manager_->GetAcceleratedWidgetAtScreenPoint(point);
}

display::Display HaikuScreen::GetDisplayNearestPoint(
    const gfx::Point& point) const {
  return GetPrimaryDisplay();
}

display::Display HaikuScreen::GetDisplayMatching(
    const gfx::Rect& match_rect) const {
  return GetPrimaryDisplay();
}

void HaikuScreen::AddObserver(display::DisplayObserver* observer) {
  display_list_.AddObserver(observer);
}

void HaikuScreen::RemoveObserver(display::DisplayObserver* observer) {
  display_list_.RemoveObserver(observer);
}

}  // namespace ui
