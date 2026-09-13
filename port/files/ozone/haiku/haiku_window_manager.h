// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef UI_OZONE_PLATFORM_HAIKU_HAIKU_WINDOW_MANAGER_H_
#define UI_OZONE_PLATFORM_HAIKU_HAIKU_WINDOW_MANAGER_H_

#include "base/containers/id_map.h"
#include "base/threading/thread_checker.h"
#include "ui/gfx/geometry/point.h"
#include "ui/gfx/native_ui_types.h"

namespace ui {

class HaikuWindow;

// Maps the AcceleratedWidget ids Chromium hands around onto the windows they
// name. The surface factory needs this because it is given only a widget id
// and has to find the view to draw into.
class HaikuWindowManager {
 public:
  HaikuWindowManager();

  HaikuWindowManager(const HaikuWindowManager&) = delete;
  HaikuWindowManager& operator=(const HaikuWindowManager&) = delete;

  ~HaikuWindowManager();

  gfx::AcceleratedWidget AddWindow(HaikuWindow* window);
  void RemoveWindow(gfx::AcceleratedWidget widget, HaikuWindow* window);
  HaikuWindow* GetWindow(gfx::AcceleratedWidget widget);

  gfx::AcceleratedWidget GetAcceleratedWidgetAtScreenPoint(
      const gfx::Point& point);

 private:
  base::IDMap<HaikuWindow*> windows_;
  base::ThreadChecker thread_checker_;
};

}  // namespace ui

#endif  // UI_OZONE_PLATFORM_HAIKU_HAIKU_WINDOW_MANAGER_H_
