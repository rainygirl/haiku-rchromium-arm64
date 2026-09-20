// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// The per-OS half of base::Process. Linux reads /proc and moves processes
// between cgroups; Haiku has neither, and schedules by thread priority rather
// than by team, so priority is reported as the one value there is and cannot
// be changed. Start time comes from the team's own info.

#include "base/process/process.h"

#include <OS.h>

#include "base/time/time.h"

namespace base {

Time Process::CreationTime() const {
  team_info info;
  if (get_team_info(Pid(), &info) != B_OK) {
    return Time();
  }
  // team_info::start_time is a bigtime_t of microseconds since the epoch,
  // which is what Time::FromTimeT's finer-grained sibling wants.
  return Time::FromDeltaSinceWindowsEpoch(
      Microseconds(info.start_time) +
      Time::UnixEpoch().ToDeltaSinceWindowsEpoch());
}

// static
bool Process::CanSetPriority() {
  return false;
}

Process::Priority Process::GetPriority() const {
  DCHECK(IsValid());
  return Priority::kUserBlocking;
}

bool Process::SetPriority(Priority priority) {
  // Nothing to set: see the file comment.
  return false;
}

}  // namespace base
