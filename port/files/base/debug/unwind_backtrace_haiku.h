// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef BASE_DEBUG_UNWIND_BACKTRACE_HAIKU_H_
#define BASE_DEBUG_UNWIND_BACKTRACE_HAIKU_H_

// backtrace() for Haiku.
//
// stack_trace_posix.cc reaches for <execinfo.h>, which on Haiku is the
// HaikuPorts libexecinfo package rather than part of the base system, so
// HAVE_BACKTRACE is unset and every crash printed "[end of stack trace]" with
// nothing above it.
//
// Nothing extra is needed to unwind, though: the build already emits
// .eh_frame, and libc++abi already links an unwinder, so _Unwind_Backtrace
// walks the stack with no package and no frame pointers.
//
// Symbolisation is left to the host. A Haiku executable is ET_DYN, so a
// runtime address means nothing on its own; the image map printed alongside
// gives each image's load address, and an address minus its image's base is
// the file offset to hand to addr2line.

#include <image.h>
#include <unistd.h>
#include <unwind.h>

#include <array>
#include <cstddef>
#include <cstdint>
#include <string_view>

#include "base/containers/span.h"
#include "base/strings/cstring_view.h"

namespace base {
namespace debug {
namespace haiku {

namespace internal {

struct UnwindState {
  span<const void*> trace;
  size_t count = 0;
  // _Unwind_Backtrace starts at its own caller, which is inside this file.
  // That frame says nothing about where the crash happened.
  size_t skip = 1;
};

inline _Unwind_Reason_Code UnwindOneFrame(struct _Unwind_Context* context,
                                          void* arg) {
  UnwindState* state = static_cast<UnwindState*>(arg);
  const uintptr_t ip = _Unwind_GetIP(context);
  if (ip == 0) {
    return _URC_END_OF_STACK;
  }
  if (state->skip > 0) {
    --state->skip;
    return _URC_NO_REASON;
  }
  if (state->count >= state->trace.size()) {
    return _URC_END_OF_STACK;
  }
  state->trace[state->count++] = reinterpret_cast<const void*>(ip);
  return _URC_NO_REASON;
}

// The write() below is what makes this usable from a signal handler: no
// malloc, no stdio.
inline void WriteStderr(span<const char> text) {
  const ssize_t written = write(STDERR_FILENO, text.data(), text.size());
  (void)written;
}

inline void WriteStderr(cstring_view text) {
  WriteStderr(span(text));
}

// Writes "0x" plus `value` in hex into `out`, and returns the part written.
inline span<const char> FormatHex(span<char, 2 + 2 * sizeof(uintptr_t)> out,
                                  uintptr_t value) {
  static constexpr cstring_view kDigits = "0123456789abcdef";
  // Fill from the end, since the low nibble is produced first.
  size_t first = out.size();
  uintptr_t remaining = value;
  do {
    out[--first] = kDigits[remaining & 0xf];
    remaining >>= 4;
  } while (remaining != 0 && first > 2);
  out[--first] = 'x';
  out[--first] = '0';
  return out.subspan(first);
}

// A Haiku image name is a fixed-size array that may or may not fill up.
inline span<const char> ImageName(const image_info& info) {
  auto name = span(info.name);
  size_t length = 0;
  while (length < name.size() && name[length] != '\0') {
    ++length;
  }
  return name.first(length);
}

}  // namespace internal

// Fills `trace` with return addresses and returns how many were written.
inline size_t CollectBacktrace(span<const void*> trace) {
  if (trace.empty()) {
    return 0;
  }
  internal::UnwindState state{trace};
  _Unwind_Backtrace(&internal::UnwindOneFrame, &state);
  return state.count;
}

// One line per loaded image: where its text was mapped, how long it is, and
// which file it came from. Without this the addresses below are unusable.
inline void PrintImageMap(cstring_view prefix) {
  int32 cookie = 0;
  image_info info;
  while (get_next_image_info(B_CURRENT_TEAM, &cookie, &info) == B_OK) {
    std::array<char, 2 + 2 * sizeof(uintptr_t)> buffer;
    internal::WriteStderr(prefix);
    internal::WriteStderr(cstring_view("image "));
    internal::WriteStderr(internal::FormatHex(
        buffer, reinterpret_cast<uintptr_t>(info.text)));
    internal::WriteStderr(cstring_view("+"));
    internal::WriteStderr(
        internal::FormatHex(buffer, static_cast<uintptr_t>(info.text_size)));
    internal::WriteStderr(cstring_view(" "));
    internal::WriteStderr(internal::ImageName(info));
    internal::WriteStderr(cstring_view("\n"));
  }
}

inline void PrintBacktrace(span<const void* const> trace,
                           cstring_view prefix) {
  PrintImageMap(prefix);
  for (const void* address : trace) {
    std::array<char, 2 + 2 * sizeof(uintptr_t)> buffer;
    internal::WriteStderr(prefix);
    internal::WriteStderr(
        internal::FormatHex(buffer, reinterpret_cast<uintptr_t>(address)));
    internal::WriteStderr(cstring_view("\n"));
  }
}

// The same map for the std::ostream path, which is not signal-handler code
// and can afford the stream. Templated only to keep <ostream> out of here.
template <typename Stream>
void PrintImageMapToStream(Stream* os, cstring_view prefix) {
  int32 cookie = 0;
  image_info info;
  while (get_next_image_info(B_CURRENT_TEAM, &cookie, &info) == B_OK) {
    const auto name = internal::ImageName(info);
    *os << prefix << "image " << info.text << "+" << info.text_size << " "
        << std::string_view(name.data(), name.size()) << "\n";
  }
}

}  // namespace haiku
}  // namespace debug
}  // namespace base

#endif  // BASE_DEBUG_UNWIND_BACKTRACE_HAIKU_H_
