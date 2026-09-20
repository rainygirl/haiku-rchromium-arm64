// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "ui/ozone/platform/haiku/haiku_surface_factory.h"

#include <Bitmap.h>
#include <GraphicsDefs.h>

#include <memory>

#include "base/compiler_specific.h"
#include "base/memory/scoped_refptr.h"
#include "skia/ext/legacy_display_globals.h"
#include "third_party/skia/include/core/SkCanvas.h"
#include "third_party/skia/include/core/SkImageInfo.h"
#include "third_party/skia/include/core/SkPixmap.h"
#include "third_party/skia/include/core/SkSurface.h"
#include "third_party/skia/include/core/SkSurfaceProps.h"
#include "ui/gfx/geometry/rect.h"
#include "ui/gfx/geometry/size.h"
#include "ui/gfx/vsync_provider.h"
#include "ui/ozone/platform/haiku/haiku_window.h"
#include "ui/ozone/platform/haiku/haiku_window_manager.h"
#include "ui/ozone/public/surface_ozone_canvas.h"

namespace ui {

namespace {

// Skia's N32 premultiplied layout is BGRA on little-endian, which is exactly
// B_RGBA32 -- so the copy below is a straight memcpy per row with no channel
// swizzling.
class HaikuCanvasSurface : public SurfaceOzoneCanvas {
 public:
  explicit HaikuCanvasSurface(scoped_refptr<HaikuPresentTarget> target)
      : target_(std::move(target)) {}

  ~HaikuCanvasSurface() override = default;

  void ResizeCanvas(const gfx::Size& viewport_size, float scale) override {
    size_ = viewport_size;
    SkSurfaceProps props = skia::LegacyDisplayGlobals::GetSkSurfaceProps();
    surface_ = SkSurfaces::Raster(
        SkImageInfo::MakeN32Premul(viewport_size.width(),
                                   viewport_size.height()),
        &props);
  }

  SkCanvas* GetCanvas() override {
    return surface_ ? surface_->getCanvas() : nullptr;
  }

  void PresentCanvas(const gfx::Rect& damage) override {
    if (!surface_ || !target_) {
      return;
    }
    SkPixmap pixmap;
    if (!surface_->peekPixels(&pixmap)) {
      return;
    }

    BRect bounds(0, 0, size_.width() - 1, size_.height() - 1);
    auto bitmap = std::make_unique<BBitmap>(bounds, B_RGBA32);
    if (bitmap->InitCheck() != B_OK) {
      return;
    }

    const int32 dst_stride = bitmap->BytesPerRow();
    const size_t src_stride = pixmap.rowBytes();
    const size_t row_bytes =
        static_cast<size_t>(size_.width()) * 4u;
    auto* dst = static_cast<uint8_t*>(bitmap->Bits());
    const auto* src = static_cast<const uint8_t*>(pixmap.addr());
    // SAFETY: dst is BBitmap::Bits(), sized dst_stride * size_.height() by
    // BBitmap's own allocation for these `bounds`; src is the raster
    // surface's pixels, sized src_stride * size_.height() by the
    // SkSurfaces::Raster() call in ResizeCanvas() above with this same
    // size_. row_bytes (width * 4, RGBA8) is <= both strides, and y is
    // bounded by size_.height(), so every access stays within both buffers.
    for (int y = 0; y < size_.height(); ++y) {
      UNSAFE_BUFFERS(memcpy(dst + static_cast<size_t>(y) * dst_stride,
                            src + static_cast<size_t>(y) * src_stride,
                            row_bytes));
    }

    // The window takes ownership; it holds the bitmap as its front buffer so
    // that expose events can repaint without a new frame. This runs on the
    // compositor thread, which is why the handle is a HaikuPresentTarget and
    // not a base::WeakPtr -- see haiku_window.h.
    target_->Present(bitmap.release(), damage);
  }

  std::unique_ptr<gfx::VSyncProvider> CreateVSyncProvider() override {
    return nullptr;
  }

 private:
  scoped_refptr<HaikuPresentTarget> target_;
  sk_sp<SkSurface> surface_;
  gfx::Size size_;
};

}  // namespace

HaikuSurfaceFactory::HaikuSurfaceFactory(HaikuWindowManager* window_manager)
    : window_manager_(window_manager) {}

HaikuSurfaceFactory::~HaikuSurfaceFactory() = default;

std::vector<gl::GLImplementationParts>
HaikuSurfaceFactory::GetAllowedGLImplementations() {
  // Empty: there is no GL on this platform, so the compositor falls back to
  // the software path rather than probing for a driver that is not there.
  return {};
}

GLOzone* HaikuSurfaceFactory::GetGLOzone(
    const gl::GLImplementationParts& implementation) {
  return nullptr;
}

std::unique_ptr<SurfaceOzoneCanvas> HaikuSurfaceFactory::CreateCanvasForWidget(
    gfx::AcceleratedWidget widget) {
  // Null in a GPU process: InitializeGPU() builds this factory without a
  // window manager because the windows are in the browser process. Chrome
  // asks for viz to run in-process on this platform for that reason, but a
  // command line can still put it in a process of its own, and returning no
  // canvas is a great deal better than dereferencing nothing.
  if (!window_manager_) {
    return nullptr;
  }
  HaikuWindow* window = window_manager_->GetWindow(widget);
  if (!window) {
    return nullptr;
  }
  return std::make_unique<HaikuCanvasSurface>(window->present_target());
}

}  // namespace ui
