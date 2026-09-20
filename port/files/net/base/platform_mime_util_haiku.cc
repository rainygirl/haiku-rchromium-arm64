// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Platform MIME lookups. Linux consults the XDG shared MIME database; Haiku
// keeps its own in the BMimeType registry, which //net must not reach for
// (libbe belongs to the ozone layer). Chromium's built-in table stays the
// only source, which is what these two "not found" answers mean.

#include "net/base/platform_mime_util.h"

#include <string>

namespace net {

bool PlatformMimeUtil::GetPlatformMimeTypeFromExtension(
    const base::FilePath::StringType& ext,
    std::string* result) const {
  return false;
}

bool PlatformMimeUtil::GetPlatformPreferredExtensionForMimeType(
    std::string_view mime_type,
    base::FilePath::StringType* extension) const {
  return false;
}

void PlatformMimeUtil::GetPlatformExtensionsForMimeType(
    std::string_view mime_type,
    std::unordered_set<base::FilePath::StringType>* extensions) const {}

}  // namespace net
