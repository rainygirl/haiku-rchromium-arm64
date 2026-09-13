// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "base/process/process_metrics.h"

#include <OS.h>

namespace base {

// Haiku reports system memory through get_system_info(), in pages. There is
// no /proc/meminfo to parse.
//
//   max_pages     total accessible pages
//   used_pages    of those, in use
//   cached_pages  file cache, reclaimable under pressure
//
// Only `total` and `free` are filled in: SystemMemoryInfo declares `cached`
// and `available` only for the platforms whose /proc/meminfo supplies them,
// and Haiku is not one of them. The cache figure is still used, to work out
// what is actually free -- pages held by the file cache are reclaimable, so
// counting them as in-use would understate free memory badly.
bool GetSystemMemoryInfo(SystemMemoryInfo* meminfo) {
  system_info info;
  if (get_system_info(&info) != B_OK) {
    return false;
  }

  const uint64_t page_size = static_cast<uint64_t>(B_PAGE_SIZE);
  const uint64_t total = info.max_pages * page_size;
  const uint64_t used = info.used_pages * page_size;
  const uint64_t cached = info.cached_pages * page_size;
  const uint64_t in_use = used > cached ? used - cached : 0;

  meminfo->total = ByteSize(total);
  meminfo->free = ByteSize(total > in_use ? total - in_use : 0);

  return true;
}

}  // namespace base
