// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// The responsiveness calculator wants to know when the UI thread starts and
// finishes handling a native event. On Linux that hooks into the X11/Wayland
// event source; on Haiku the events arrive on the BWindow's own looper thread
// inside the ozone layer, which this code cannot reach, so nothing is
// observed and the calculator simply sees no native-event phases.

#include "content/browser/scheduler/responsiveness/native_event_observer.h"

namespace content {
namespace responsiveness {

void BrowserUINativeEventObserver::RegisterObserver() {}

void BrowserUINativeEventObserver::UnregisterObserver() {}

}  // namespace responsiveness
}  // namespace content
