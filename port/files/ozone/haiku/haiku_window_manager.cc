// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "ui/ozone/platform/haiku/haiku_window_manager.h"

#include "base/check.h"
#include "ui/ozone/platform/haiku/haiku_window.h"

namespace ui {

HaikuWindowManager::HaikuWindowManager() = default;

HaikuWindowManager::~HaikuWindowManager() = default;

gfx::AcceleratedWidget HaikuWindowManager::AddWindow(HaikuWindow* window) {
  DCHECK(thread_checker_.CalledOnValidThread());
  return static_cast<gfx::AcceleratedWidget>(windows_.Add(window));
}

void HaikuWindowManager::RemoveWindow(gfx::AcceleratedWidget widget,
                                      HaikuWindow* window) {
  DCHECK(thread_checker_.CalledOnValidThread());
  DCHECK_EQ(window, windows_.Lookup(static_cast<int32_t>(widget)));
  windows_.Remove(static_cast<int32_t>(widget));
}

HaikuWindow* HaikuWindowManager::GetWindow(gfx::AcceleratedWidget widget) {
  DCHECK(thread_checker_.CalledOnValidThread());
  return windows_.Lookup(static_cast<int32_t>(widget));
}

gfx::AcceleratedWidget HaikuWindowManager::GetAcceleratedWidgetAtScreenPoint(
    const gfx::Point& point) {
  DCHECK(thread_checker_.CalledOnValidThread());
  // Topmost wins, and IDMap iterates oldest first, so keep the last match
  // rather than returning on the first one.
  gfx::AcceleratedWidget found = gfx::kNullAcceleratedWidget;
  for (base::IDMap<HaikuWindow*>::iterator it(&windows_); !it.IsAtEnd();
       it.Advance()) {
    if (it.GetCurrentValue()->GetBoundsInPixels().Contains(point)) {
      found = static_cast<gfx::AcceleratedWidget>(it.GetCurrentKey());
    }
  }
  return found;
}

}  // namespace ui
