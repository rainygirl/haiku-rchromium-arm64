// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef UI_OZONE_PLATFORM_HAIKU_HAIKU_SCREEN_H_
#define UI_OZONE_PLATFORM_HAIKU_HAIKU_SCREEN_H_

#include <vector>

#include "base/memory/raw_ptr.h"
#include "ui/display/display.h"
#include "ui/display/display_list.h"
#include "ui/ozone/public/platform_screen.h"

namespace ui {

class HaikuWindowManager;

// One display, described by BScreen. Haiku supports multiple monitors, but
// BScreen enumerates them by index only through screen_id, which the public
// API does not expose usefully; a single display is what app_server reports
// for the common case and is what this reads.
class HaikuScreen : public PlatformScreen {
 public:
  explicit HaikuScreen(HaikuWindowManager* window_manager);

  HaikuScreen(const HaikuScreen&) = delete;
  HaikuScreen& operator=(const HaikuScreen&) = delete;

  ~HaikuScreen() override;

  // PlatformScreen:
  const std::vector<display::Display>& GetAllDisplays() const override;
  display::Display GetPrimaryDisplay() const override;
  display::Display GetDisplayForAcceleratedWidget(
      gfx::AcceleratedWidget widget) const override;
  gfx::Point GetCursorScreenPoint() const override;
  gfx::AcceleratedWidget GetAcceleratedWidgetAtScreenPoint(
      const gfx::Point& point) const override;
  display::Display GetDisplayNearestPoint(
      const gfx::Point& point) const override;
  display::Display GetDisplayMatching(
      const gfx::Rect& match_rect) const override;
  void AddObserver(display::DisplayObserver* observer) override;
  void RemoveObserver(display::DisplayObserver* observer) override;

 private:
  raw_ptr<HaikuWindowManager> window_manager_;
  display::DisplayList display_list_;
};

}  // namespace ui

#endif  // UI_OZONE_PLATFORM_HAIKU_HAIKU_SCREEN_H_
