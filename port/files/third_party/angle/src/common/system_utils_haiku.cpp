// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// The one system utility ANGLE keeps in its Linux file rather than its POSIX
// one. Haiku names threads with rename_thread() instead of prctl().

#include "common/system_utils.h"

#include <OS.h>

namespace angle
{
void SetCurrentThreadName(const char *name)
{
    rename_thread(find_thread(nullptr), name);
}
}  // namespace angle
