// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// PartitionAlloc's own stack collector. It has to be async-signal safe, so it
// cannot call into anything that allocates -- and Haiku keeps backtrace() in
// libexecinfo, which is not part of the base system and which //base does not
// link. Collect nothing; the allocator's debugging output then carries no
// stacks, which is what every platform without frame-pointer unwinding gets.

#include "partition_alloc/partition_alloc_base/debug/stack_trace.h"

namespace partition_alloc::internal::base::debug {

size_t CollectStackTrace(const void** trace, size_t count) {
  return 0;
}

}  // namespace partition_alloc::internal::base::debug
