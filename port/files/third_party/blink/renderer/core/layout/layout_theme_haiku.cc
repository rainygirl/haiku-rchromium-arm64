// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Form controls and scrollbars. Blink's default theme is what every platform
// without its own native drawing uses; Haiku's controls come from
// BControlLook in the toolbar, not from inside the page.

#include "third_party/blink/renderer/core/layout/layout_theme_default.h"

namespace blink {

namespace {

class LayoutThemeHaiku final : public LayoutThemeDefault {
 public:
  static scoped_refptr<LayoutTheme> Create() {
    return base::AdoptRef(new LayoutThemeHaiku());
  }
};

}  // namespace

LayoutTheme& LayoutTheme::NativeTheme() {
  DEFINE_STATIC_REF(LayoutTheme, layout_theme, (LayoutThemeHaiku::Create()));
  return *layout_theme;
}

}  // namespace blink
