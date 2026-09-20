// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "ui/ozone/platform/haiku/haiku_window_manager.h"

#include "base/check_op.h"
#include "base/synchronization/lock.h"
#include "ui/ozone/platform/haiku/haiku_window.h"

namespace ui {

HaikuWindowManager::HaikuWindowManager() = default;

HaikuWindowManager::~HaikuWindowManager() = default;

gfx::AcceleratedWidget HaikuWindowManager::AddWindow(HaikuWindow* window) {
  base::AutoLock guard(lock_);
  const int32_t id = next_id_++;
  windows_[id] = window;
  return static_cast<gfx::AcceleratedWidget>(id);
}

void HaikuWindowManager::RemoveWindow(gfx::AcceleratedWidget widget,
                                      HaikuWindow* window) {
  base::AutoLock guard(lock_);
  auto it = windows_.find(static_cast<int32_t>(widget));
  DCHECK(it != windows_.end());
  DCHECK_EQ(window, it->second);
  windows_.erase(it);
}

HaikuWindow* HaikuWindowManager::GetWindow(gfx::AcceleratedWidget widget) {
  base::AutoLock guard(lock_);
  auto it = windows_.find(static_cast<int32_t>(widget));
  return it == windows_.end() ? nullptr : it->second;
}

gfx::AcceleratedWidget HaikuWindowManager::GetAcceleratedWidgetAtScreenPoint(
    const gfx::Point& point) {
  base::AutoLock guard(lock_);
  // Topmost wins, and the map iterates in id order, which is creation order,
  // so keep the last match rather than returning on the first one.
  gfx::AcceleratedWidget found = gfx::kNullAcceleratedWidget;
  for (const auto& entry : windows_) {
    if (entry.second->GetBoundsInPixels().Contains(point)) {
      found = static_cast<gfx::AcceleratedWidget>(entry.first);
    }
  }
  return found;
}

}  // namespace ui
