// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "ui/ozone/platform/haiku/client_native_pixmap_factory_haiku.h"

#include "ui/gfx/linux/client_native_pixmap_factory_dmabuf.h"

namespace ui {

gfx::ClientNativePixmapFactory* CreateClientNativePixmapFactoryHaiku() {
  // There are no native pixmaps without a GPU driver, and nothing in the
  // software path asks for one.
  return nullptr;
}

}  // namespace ui
