// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Per-process memory figures for the memory-instrumentation service. Haiku
// has no /proc; get_team_usage_info() reports CPU time but no resident size,
// and the area API would have to be walked per team to total one up. Until
// something needs the numbers, report that they are unavailable -- the
// service then omits the process from the dump rather than reporting zeros as
// if they were measured.

#include "services/resource_coordinator/public/cpp/memory_instrumentation/os_metrics.h"

#include <vector>

#include "base/notimplemented.h"
#include "base/process/process_handle.h"

namespace memory_instrumentation {

// static
bool OSMetrics::FillOSMemoryDump(base::ProcessHandle handle,
                                 const MemDumpFlagSet& flags,
                                 mojom::RawOSMemDump* dump) {
  return false;
}

// static
std::vector<mojom::VmRegionPtr> OSMetrics::GetProcessMemoryMaps(
    base::ProcessHandle) {
  NOTIMPLEMENTED();
  return std::vector<mojom::VmRegionPtr>();
}

}  // namespace memory_instrumentation
