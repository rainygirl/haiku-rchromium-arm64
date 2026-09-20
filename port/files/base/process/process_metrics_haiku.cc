// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "base/process/process_metrics.h"

#include <memory>

#include "base/memory/ptr_util.h"
#include "base/process/process_handle.h"
#include "base/time/time.h"

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


// The process-level metrics. Haiku's get_team_usage_info() reports the team's
// accumulated user and kernel time, which is what GetCumulativeCPUUsage is
// after; there is no equivalent of /proc/<pid>/stat for the rest.
ProcessMetrics::ProcessMetrics(ProcessHandle process) : process_(process) {}

// static
std::unique_ptr<ProcessMetrics> ProcessMetrics::CreateProcessMetrics(
    ProcessHandle process) {
  return base::WrapUnique(new ProcessMetrics(process));
}

base::expected<TimeDelta, ProcessCPUUsageError>
ProcessMetrics::GetCumulativeCPUUsage() {
  team_usage_info usage;
  const team_id team =
      process_ == base::kNullProcessHandle ? B_CURRENT_TEAM : process_;
  if (get_team_usage_info(team, B_TEAM_USAGE_SELF, &usage) != B_OK) {
    return base::unexpected(ProcessCPUUsageError::kSystemError);
  }
  // Both fields are bigtime_t, i.e. microseconds.
  return base::ok(Microseconds(usage.user_time + usage.kernel_time));
}


// Per-process memory. Haiku has no /proc/<pid>/statm; totalling a team's
// areas through get_next_area_info() would count shared pages once per area,
// which is worse than saying "unavailable" -- the callers all treat the error
// as "no figure for this process".
base::expected<ProcessMemoryInfo, ProcessUsageError>
ProcessMetrics::GetMemoryInfo() const {
  return base::unexpected(ProcessUsageError::kSystemError);
}

ProcessId GetParentProcessId(ProcessHandle process) {
  team_info info;
  if (get_team_info(process, &info) != B_OK) {
    return kNullProcessId;
  }
  return info.parent;
}

}  // namespace base
