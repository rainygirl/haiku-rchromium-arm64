// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Linux watches /etc/localtime for time-zone changes through inotify. Haiku
// keeps its setting elsewhere and has no file to watch from here, so the
// monitor exists but never fires -- a time-zone change is picked up on the
// next restart, which is what the Fuchsia implementation also settles for.

#include "services/device/time_zone_monitor/time_zone_monitor.h"

#include <memory>

namespace device {

namespace {

class TimeZoneMonitorHaiku : public TimeZoneMonitor {
 public:
  TimeZoneMonitorHaiku() = default;
  TimeZoneMonitorHaiku(const TimeZoneMonitorHaiku&) = delete;
  TimeZoneMonitorHaiku& operator=(const TimeZoneMonitorHaiku&) = delete;
  ~TimeZoneMonitorHaiku() override = default;
};

}  // namespace

// static
std::unique_ptr<TimeZoneMonitor> TimeZoneMonitor::Create(
    scoped_refptr<base::SequencedTaskRunner> file_task_runner) {
  return std::make_unique<TimeZoneMonitorHaiku>();
}

}  // namespace device
