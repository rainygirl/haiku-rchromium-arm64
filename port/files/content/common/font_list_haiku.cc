// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "content/common/font_list.h"

#include "base/values.h"

namespace content {

// Haiku has no fontconfig, and //content/common must not link libbe: the list
// is only used to populate a font picker in the settings UI, which
// content_shell does not have. Blink finds its fonts through the Haiku font
// manager in //ui/ozone, not through this. An enumeration over
// count_font_families()/get_font_family() would go here if something ever
// needs the list.
base::ListValue GetFontList_SlowBlocking() {
  return base::ListValue();
}

}  // namespace content
