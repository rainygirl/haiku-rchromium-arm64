// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// There is no GL on Haiku, so there is no native GL surface to hand the
// compositor: it composites in software and presents through the BeAPI shim
// (see //ui/ozone/platform/haiku). Only the stub surface a mock GL
// implementation asks for is answered here, as on Fuchsia.

#include "gpu/ipc/service/image_transport_surface.h"

#include "ui/gl/gl_surface.h"
#include "ui/gl/gl_surface_stub.h"
#include "ui/gl/init/gl_factory.h"

namespace gpu {

// static
scoped_refptr<gl::Presenter> ImageTransportSurface::CreatePresenter(
    scoped_refptr<SharedContextState> context_state,
    const GpuDriverBugWorkarounds& workarounds,
    const GpuFeatureInfo& gpu_feature_info,
    SurfaceHandle surface_handle) {
  return nullptr;
}

// static
scoped_refptr<gl::GLSurface> ImageTransportSurface::CreateNativeGLSurface(
    gl::GLDisplay* display,
    SurfaceHandle surface_handle,
    gl::GLSurfaceFormat format) {
  if (gl::GetGLImplementation() == gl::kGLImplementationMockGL ||
      gl::GetGLImplementation() == gl::kGLImplementationStubGL) {
    return new gl::GLSurfaceStub;
  }
  return nullptr;
}

}  // namespace gpu
