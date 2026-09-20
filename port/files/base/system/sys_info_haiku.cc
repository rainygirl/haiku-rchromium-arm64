// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// System facts. Linux reads /proc/meminfo and /proc/cpuinfo; Haiku answers
// the memory question from get_system_info(), and has no CPU name to report.

#include "base/system/sys_info.h"

#include <OS.h>

#include <string>

#include "base/byte_size.h"

namespace base {

namespace {

ByteSize PageBytes(uint64_t pages) {
  return ByteSize(pages * static_cast<uint64_t>(B_PAGE_SIZE));
}

}  // namespace

// static
ByteSize SysInfo::AmountOfTotalPhysicalMemoryImpl() {
  system_info info;
  if (get_system_info(&info) != B_OK) {
    return ByteSize(0);
  }
  return PageBytes(info.max_pages);
}

// static
ByteSize SysInfo::AmountOfAvailablePhysicalMemoryImpl() {
  system_info info;
  if (get_system_info(&info) != B_OK) {
    return ByteSize(0);
  }
  // Pages held by the file cache are reclaimable, so they count as available;
  // counting only untouched pages would understate this badly.
  const uint64_t used = info.used_pages > info.cached_pages
                            ? info.used_pages - info.cached_pages
                            : 0;
  return PageBytes(info.max_pages - used);
}

// static
std::string SysInfo::CPUModelName() {
  // get_system_info() carries a cpu_type enum, not a marketing string, and on
  // arm64 it does not identify the part at all. Callers read an empty string
  // as "unknown".
  return std::string();
}

}  // namespace base
