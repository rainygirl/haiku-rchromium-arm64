// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef UI_OZONE_PLATFORM_HAIKU_OZONE_PLATFORM_HAIKU_H_
#define UI_OZONE_PLATFORM_HAIKU_OZONE_PLATFORM_HAIKU_H_

namespace ui {

class OzonePlatform;

// Constructed by the generated constructor list; the name is derived from the
// platform name in ui/ozone/BUILD.gn.
OzonePlatform* CreateOzonePlatformHaiku();

}  // namespace ui

#endif  // UI_OZONE_PLATFORM_HAIKU_OZONE_PLATFORM_HAIKU_H_
