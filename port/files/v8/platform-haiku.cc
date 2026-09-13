// Copyright 2012 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Platform-specific code for Haiku goes here. For the POSIX-compatible
// parts, the implementation is in platform-posix.cc.

#include <errno.h>
#include <pthread.h>
#include <semaphore.h>
#include <signal.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/time.h>
#include <sys/types.h>
#include <unistd.h>

#include <kernel/image.h>

#include <cmath>

#undef MAP_TYPE

#include "src/base/macros.h"
#include "src/base/platform/platform-posix-time.h"
#include "src/base/platform/platform-posix.h"
#include "src/base/platform/platform.h"

namespace v8 {
namespace base {

TimezoneCache* OS::CreateTimezoneCache() {
  return new PosixDefaultTimezoneCache();
}

std::vector<OS::SharedLibraryAddress> OS::GetSharedLibraryAddresses() {
  // Haiku has no /proc/self/maps. The kernel enumerates loaded images
  // directly, and each one reports the address and size of its text
  // segment -- which is exactly what the profiler needs to attribute a
  // sample to a library.
  std::vector<SharedLibraryAddress> result;
  image_info info;
  int32 cookie = 0;
  while (get_next_image_info(B_CURRENT_TEAM, &cookie, &info) == B_OK) {
    const uintptr_t start = reinterpret_cast<uintptr_t>(info.text);
    if (start == 0 || info.text_size <= 0) continue;
    result.push_back(SharedLibraryAddress(
        info.name, start, start + static_cast<uintptr_t>(info.text_size)));
  }
  return result;
}

void OS::SignalCodeMovingGC() {
  // The Linux implementation writes a marker mmap that ll_prof.py looks for
  // in the kernel's mmap log. Haiku keeps no such log, so there is nothing
  // to synchronise against and nothing useful to do here.
}

void OS::AdjustSchedulingParams() {}

std::optional<OS::MemoryRange> OS::GetFirstFreeMemoryRangeWithin(
    OS::Address boundary_start, OS::Address boundary_end, size_t minimum_size,
    size_t alignment) {
  return std::nullopt;
}

}  // namespace base
}  // namespace v8
