// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Haiku has no sandbox: no seccomp-bpf, no namespaces, no setuid helper. The
// renderer therefore runs with the same rights as the browser, which is why
// the launcher passes --no-sandbox, and why this reports that no sandbox was
// enabled rather than pretending otherwise.

#include "content/renderer/renderer_main_platform_delegate.h"

namespace content {

RendererMainPlatformDelegate::RendererMainPlatformDelegate(
    const MainFunctionParams& parameters) {}

RendererMainPlatformDelegate::~RendererMainPlatformDelegate() = default;

void RendererMainPlatformDelegate::PlatformInitialize() {}

void RendererMainPlatformDelegate::PlatformUninitialize() {}

bool RendererMainPlatformDelegate::EnableSandbox() {
  return false;
}

}  // namespace content
