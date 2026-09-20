// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef UI_OZONE_PLATFORM_HAIKU_HAIKU_WINDOW_MANAGER_H_
#define UI_OZONE_PLATFORM_HAIKU_HAIKU_WINDOW_MANAGER_H_

#include <stdint.h>

#include <map>

#include "base/synchronization/lock.h"
#include "base/thread_annotations.h"
#include "ui/gfx/geometry/point.h"
#include "ui/gfx/native_ui_types.h"

namespace ui {

class HaikuWindow;

// Maps the AcceleratedWidget ids Chromium hands around onto the windows they
// name. The surface factory needs this because it is given only a widget id
// and has to find the view to draw into.
//
// It is read from more than one thread and has to be. Windows are added and
// removed on the UI thread, while viz calls CreateCanvasForWidget() -- and so
// GetWindow() -- on the compositor thread. This class used to hold a
// base::IDMap and assert the opposite with a ThreadChecker, which said nothing
// in a release build and left an unsynchronised hash map open to a concurrent
// insert and lookup. The dcheck_always_on build of 2026-09-20 said so on the
// first frame: "haiku_window_manager.cc:29 DCHECK failed:
// thread_checker_.CalledOnValidThread()".
//
// base::IDMap is not the container to lock around, either: it carries its own
// SEQUENCE_CHECKER on every method, so it means the same single-sequence
// promise this class cannot keep. A plain std::map under a lock does. Ids
// count up from 1 so that none of them is gfx::kNullAcceleratedWidget, and
// std::map iterates in id order, which is creation order -- what
// GetAcceleratedWidgetAtScreenPoint()'s "topmost wins" rule reads.
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
  base::Lock lock_;
  int32_t next_id_ GUARDED_BY(lock_) = 1;
  std::map<int32_t, HaikuWindow*> windows_ GUARDED_BY(lock_);
};

}  // namespace ui

#endif  // UI_OZONE_PLATFORM_HAIKU_HAIKU_WINDOW_MANAGER_H_
