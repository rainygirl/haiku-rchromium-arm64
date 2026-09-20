// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Haiku has no system-wide "reduce motion" or "smooth scrolling" preference
// that Chromium can read from here, so both answers are the defaults every
// platform without one uses.

#include "ui/gfx/animation/animation.h"

namespace gfx {

// static
bool Animation::ShouldRenderRichAnimationImpl() {
  return true;
}

// static
bool Animation::ScrollAnimationsEnabledBySystem() {
  return true;
}

// static
void Animation::UpdatePrefersReducedMotion() {
  // Haiku has no such preference to read, so the cached value stays at its
  // default of "no preference".
  prefers_reduced_motion_ = false;
}

}  // namespace gfx
