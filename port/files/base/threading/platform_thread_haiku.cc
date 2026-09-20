// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// The per-OS half of PlatformThread. Haiku names a thread with
// rename_thread() rather than prctl(PR_SET_NAME), and it schedules by thread
// priority (1..120, B_NORMAL_PRIORITY in the middle) rather than by nice
// value, so the thread-type machinery maps onto set_thread_priority().

#include "base/threading/platform_thread.h"

#include <OS.h>
#include <unistd.h>

#include <string>

#include "base/threading/platform_thread_internal_posix.h"
#include "base/threading/thread_id_name_manager.h"

namespace base {

namespace {

// What Haiku's own applications use: interactive work at the normal priority,
// background work below it, and only the audio-style threads above.
int32 HaikuPriorityForThreadType(ThreadType thread_type) {
  switch (thread_type) {
    case ThreadType::kBackground:
      return B_LOW_PRIORITY;
    case ThreadType::kUtility:
      return B_NORMAL_PRIORITY - 5;
    case ThreadType::kDefault:
      return B_NORMAL_PRIORITY;
    case ThreadType::kPresentation:
      return B_DISPLAY_PRIORITY;
    case ThreadType::kAudioProcessing:
      return B_URGENT_DISPLAY_PRIORITY;
    case ThreadType::kRealtimeAudio:
      return B_REAL_TIME_DISPLAY_PRIORITY;
  }
  return B_NORMAL_PRIORITY;
}

}  // namespace

void InitThreading() {}

void TerminateOnThread() {}

size_t GetDefaultThreadStackSize(const pthread_attr_t& attributes) {
  // Haiku gives the main thread 64 MB (USER_MAIN_THREAD_STACK_SIZE) but every
  // other thread only 256 kB (USER_STACK_SIZE). Chromium and V8 are written
  // against the glibc default of 8 MB: V8 in particular assumes it may use
  // ~1 MB before its own stack-limit check fires, so on a background parser
  // thread it would run off the end of a 256 kB stack and scribble over
  // whatever lies below it long before noticing -- which showed up as
  // corrupted AstRawStrings while parsing a large script.
  //
  // Ask for the size the rest of the code already assumes.
  return 8u * 1024 * 1024;
}

void PlatformThreadBase::SetName(const std::string& name) {
  SetNameCommon(name);

  // Renaming the main thread would rename the team, which is what Deskbar and
  // `ps` show, so leave it alone -- the same reason Linux skips it. Haiku
  // gives a team the id of its main thread, and getpid() returns the team id,
  // so that one comparison identifies it. (Comparing thread_info::team
  // instead would be true on every thread in the team, which is why no thread
  // was being renamed at all.)
  const thread_id thread = find_thread(nullptr);
  if (thread == static_cast<thread_id>(getpid())) {
    return;
  }

  // rename_thread truncates anything longer than B_OS_NAME_LENGTH itself.
  rename_thread(thread, name.c_str());
}

namespace internal {

// Haiku has no nice values; the priority is set directly instead, so nothing
// here needs a mapping table.
int ThreadTypeToNiceValue(ThreadType thread_type) {
  return 0;
}

bool CanSetThreadTypeToRealtimeAudio() {
  return true;
}

void SetCurrentThreadTypeImpl(ThreadType thread_type,
                              MessagePumpType pump_type_hint) {
  set_thread_priority(find_thread(nullptr),
                      HaikuPriorityForThreadType(thread_type));
}

// The override pair exists for Apple's pthread_override_t; elsewhere it is a
// plain bool, and raising a thread type is the same call as setting it.
PlatformPriorityOverride SetThreadTypeOverride(
    PlatformThreadHandle thread_handle,
    ThreadType thread_type) {
  return set_thread_priority(get_pthread_thread_id(thread_handle.platform_handle()),
                             HaikuPriorityForThreadType(thread_type)) >= B_OK;
}

void RemoveThreadTypeOverride(
    PlatformThreadHandle thread_handle,
    const PlatformPriorityOverride& priority_override_handle,
    ThreadType initial_thread_type) {
  set_thread_priority(get_pthread_thread_id(thread_handle.platform_handle()),
                      HaikuPriorityForThreadType(initial_thread_type));
}

}  // namespace internal

}  // namespace base
