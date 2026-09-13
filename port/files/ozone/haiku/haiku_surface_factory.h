// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef UI_OZONE_PLATFORM_HAIKU_HAIKU_SURFACE_FACTORY_H_
#define UI_OZONE_PLATFORM_HAIKU_HAIKU_SURFACE_FACTORY_H_

#include <memory>
#include <vector>

#include "base/memory/raw_ptr.h"
#include "ui/ozone/public/surface_factory_ozone.h"

namespace ui {

class HaikuWindowManager;

// Software output only. Haiku has no EGL or Vulkan driver on arm64, so there
// is nothing to accelerate against: frames are rasterised by Skia and handed
// to app_server as a BBitmap.
class HaikuSurfaceFactory : public SurfaceFactoryOzone {
 public:
  explicit HaikuSurfaceFactory(HaikuWindowManager* window_manager);

  HaikuSurfaceFactory(const HaikuSurfaceFactory&) = delete;
  HaikuSurfaceFactory& operator=(const HaikuSurfaceFactory&) = delete;

  ~HaikuSurfaceFactory() override;

  // SurfaceFactoryOzone:
  std::vector<gl::GLImplementationParts> GetAllowedGLImplementations() override;
  GLOzone* GetGLOzone(const gl::GLImplementationParts& implementation) override;
  std::unique_ptr<SurfaceOzoneCanvas> CreateCanvasForWidget(
      gfx::AcceleratedWidget widget) override;

 private:
  raw_ptr<HaikuWindowManager> window_manager_;
};

}  // namespace ui

#endif  // UI_OZONE_PLATFORM_HAIKU_HAIKU_SURFACE_FACTORY_H_
