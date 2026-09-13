// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "ui/ozone/platform/haiku/haiku_app.h"

#include "ui/ozone/platform/haiku/haiku_shim.h"

namespace ui {

// static
void HaikuApp::EnsureStarted() {
  // The BApplication runs on the shim's side of the boundary, next to the
  // windows it serves; see haiku_shim.h.
  haiku_shim::HaikuShimEnsureApp();
}

}  // namespace ui
