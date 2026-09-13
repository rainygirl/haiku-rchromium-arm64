// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef UI_OZONE_PLATFORM_HAIKU_CLIENT_NATIVE_PIXMAP_FACTORY_HAIKU_H_
#define UI_OZONE_PLATFORM_HAIKU_CLIENT_NATIVE_PIXMAP_FACTORY_HAIKU_H_

namespace gfx {
class ClientNativePixmapFactory;
}

namespace ui {

gfx::ClientNativePixmapFactory* CreateClientNativePixmapFactoryHaiku();

}  // namespace ui

#endif  // UI_OZONE_PLATFORM_HAIKU_CLIENT_NATIVE_PIXMAP_FACTORY_HAIKU_H_
