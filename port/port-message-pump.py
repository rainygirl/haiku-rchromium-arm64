#!/usr/bin/env python3
"""Make MessagePumpEpoll work on Haiku, which has no epoll.

Haiku has poll() but neither epoll nor kqueue, and Chromium removed its
libevent pump, so base/message_loop/message_pump_for_io.h maps every POSIX
platform to MessagePumpEpoll. That header reaches most of //base through
base/task/current_thread.h -- 18 of the 20 targets still failing there fail on
this one include.

Writing a poll-based pump from scratch would be about a thousand lines. It is
not necessary: MessagePumpEpoll already carries a complete poll()
implementation, GetEventsPoll(), behind the kUsePollForMessagePumpEpoll
feature. It was added for Android scheduler behaviour rather than for
portability, but it is exactly what is wanted here.

On that path epoll_event is only a struct used to carry results and the
EPOLL* values are only bit flags. So:

  * epoll_shim_haiku.h supplies the type and the constants;
  * the epoll_create/epoll_ctl/epoll_wait calls are compiled out;
  * the poll path is forced on rather than left to a feature flag.

The pump's own logic -- interests, one-shot semantics, the wake event, the
run loop -- is untouched and shared with every other platform.
"""
import os
import re
import sys

src = sys.argv[1]
H = os.path.join(src, "base/message_loop/message_pump_epoll.h")
C = os.path.join(src, "base/message_loop/message_pump_epoll.cc")

EDITS = [
    # Draining the wake-up. A real eventfd is a counter: one read empties it
    # and the descriptor stops being readable. Haiku has no eventfd, so the
    # shim uses a UDP socket connected to itself (see
    # base/message_loop/epoll_shim_haiku.h), where each ScheduleWork() queues
    # a separate 8-byte datagram and one read removes only one of them. Any
    # backlog therefore left the descriptor readable, poll() returned at once,
    # and the pump spun -- which is what had the renderer thread burning a
    # whole core with nothing rendering. Drain to EAGAIN to get the counter
    # semantics the caller assumes.
    ("base/message_loop/message_pump_epoll.cc",
     "  uint64_t value;\n"
     "  ssize_t n = HANDLE_EINTR(read(wake_event_.get(), &value, "
     "sizeof(value)));\n"
     "  DPCHECK(n == sizeof(value));\n",
     "  uint64_t value;\n"
     "  ssize_t n = HANDLE_EINTR(read(wake_event_.get(), &value, "
     "sizeof(value)));\n"
     "  DPCHECK(n == sizeof(value));\n"
     "#if defined(__HAIKU__)\n"
     "  // One datagram per ScheduleWork(), so keep reading until the socket\n"
     "  // is empty; otherwise the next poll() returns immediately forever.\n"
     "  while (HANDLE_EINTR(read(wake_event_.get(), &value, sizeof(value))) >\n"
     "         0) {\n"
     "  }\n"
     "#endif\n"),

    # With the epoll path compiled out, the buffer it reads into is unused,
    # and Chromium builds with -Werror.
    ("base/message_loop/message_pump_epoll.cc",
     "  // Used in the \"epoll\" code path.\n"
     "  epoll_event epoll_events[16];\n",
     "#if !defined(__HAIKU__)\n"
     "  // Used in the \"epoll\" code path.\n"
     "  epoll_event epoll_events[16];\n"
     "#endif\n"),

    # <sys/eventfd.h> does not exist on Haiku; epoll_shim_haiku.h supplies an
    # eventfd() of its own (a UDP socket connected to itself).
    ("base/message_loop/message_pump_epoll.cc",
     "#include <sys/eventfd.h>\n",
     "#if !defined(__HAIKU__)\n"
     "#include <sys/eventfd.h>\n"
     "#endif\n"),

    (H,
     "#include <poll.h>\n#include <sys/epoll.h>\n",
     "#include <poll.h>\n"
     "#if defined(__HAIKU__)\n"
     "#include \"base/message_loop/epoll_shim_haiku.h\"\n"
     "#else\n"
     "#include <sys/epoll.h>\n"
     "#endif\n"),

    # The epoll fd itself. Nothing reads it on the poll path.
    (C,
     "MessagePumpEpoll::MessagePumpEpoll() {\n"
     "  epoll_.reset(epoll_create1(/*flags=*/0));\n"
     "  PCHECK(epoll_.is_valid());\n",
     "MessagePumpEpoll::MessagePumpEpoll() {\n"
     "#if !defined(__HAIKU__)\n"
     "  epoll_.reset(epoll_create1(/*flags=*/0));\n"
     "  PCHECK(epoll_.is_valid());\n"
     "#endif\n"),

    (C,
     "  epoll_event wake{.events = EPOLLIN, .data = {.ptr = &wake_event_}};\n"
     "  int rv = epoll_ctl(epoll_.get(), EPOLL_CTL_ADD, wake_event_.get(), &wake);\n"
     "  PCHECK(rv == 0);\n",
     "#if !defined(__HAIKU__)\n"
     "  epoll_event wake{.events = EPOLLIN, .data = {.ptr = &wake_event_}};\n"
     "  int rv = epoll_ctl(epoll_.get(), EPOLL_CTL_ADD, wake_event_.get(), &wake);\n"
     "  PCHECK(rv == 0);\n"
     "#endif\n"),

    # Registration, modification and removal. pollfds_ is maintained beside
    # these calls already, and that is what the poll path reads.
    (C,
     "  epoll_event event{.events = events, .data = {.ptr = &entry}};\n"
     "  int rv = epoll_ctl(epoll_.get(), EPOLL_CTL_ADD, entry.fd, &event);\n",
     "#if defined(__HAIKU__)\n"
     "  int rv = 0;\n"
     "#else\n"
     "  epoll_event event{.events = events, .data = {.ptr = &entry}};\n"
     "  int rv = epoll_ctl(epoll_.get(), EPOLL_CTL_ADD, entry.fd, &event);\n"
     "#endif\n"),

    (C,
     "    epoll_event event{.events = events, .data = {.ptr = &entry}};\n"
     "    int rv = epoll_ctl(epoll_.get(), EPOLL_CTL_MOD, entry.fd, &event);\n"
     "    DPCHECK(rv == 0);\n",
     "#if !defined(__HAIKU__)\n"
     "    epoll_event event{.events = events, .data = {.ptr = &entry}};\n"
     "    int rv = epoll_ctl(epoll_.get(), EPOLL_CTL_MOD, entry.fd, &event);\n"
     "    DPCHECK(rv == 0);\n"
     "#endif\n"),

    (C,
     "    int rv = epoll_ctl(epoll_.get(), EPOLL_CTL_DEL, entry.fd, nullptr);\n"
     "    DPCHECK(rv == 0);\n",
     "#if !defined(__HAIKU__)\n"
     "    int rv = epoll_ctl(epoll_.get(), EPOLL_CTL_DEL, entry.fd, nullptr);\n"
     "    DPCHECK(rv == 0);\n"
     "#endif\n"),

    # The wait itself: take the poll branch unconditionally.
    (C,
     "  bool use_poll =\n"
     "      g_use_poll.load(std::memory_order_relaxed) && entries_.size() < 500;\n",
     "#if defined(__HAIKU__)\n"
     "  // Haiku has no epoll; the poll path is the only one.\n"
     "  const bool use_poll = true;\n"
     "#else\n"
     "  bool use_poll =\n"
     "      g_use_poll.load(std::memory_order_relaxed) && entries_.size() < 500;\n"
     "#endif\n"),

    # The whole epoll branch of the wait. On Haiku use_poll is a compile-time
    # true, so this is dead code, but it still has to compile -- and it cannot,
    # without epoll_wait.
    (C,
     "  } else {\n"
     "    const int epoll_result = epoll_wait(epoll_.get(), epoll_events,\n"
     "                                        std::size(epoll_events), epoll_timeout);\n"
     "    if (epoll_result < 0) {\n"
     "      DPCHECK(errno == EINTR);\n"
     "      return false;\n"
     "    }\n"
     "    if (epoll_result == 0) {\n"
     "      return false;\n"
     "    }\n"
     "\n"
     "    ready_events =\n"
     "        span(epoll_events).first(base::checked_cast<size_t>(epoll_result));\n"
     "  }\n",
     "  } else {\n"
     "#if defined(__HAIKU__)\n"
     "    NOTREACHED();\n"
     "#else\n"
     "    const int epoll_result = epoll_wait(epoll_.get(), epoll_events,\n"
     "                                        std::size(epoll_events), epoll_timeout);\n"
     "    if (epoll_result < 0) {\n"
     "      DPCHECK(errno == EINTR);\n"
     "      return false;\n"
     "    }\n"
     "    if (epoll_result == 0) {\n"
     "      return false;\n"
     "    }\n"
     "\n"
     "    ready_events =\n"
     "        span(epoll_events).first(base::checked_cast<size_t>(epoll_result));\n"
     "#endif\n"
     "  }\n"),
]


def main():
    applied = skipped = 0
    for path, old, new in EDITS:
        s = open(path).read()
        # An edit is done when its replacement text is present verbatim, not
        # merely when the file mentions Haiku somewhere.
        if new in s:
            skipped += 1
            continue
        n = s.count(old)
        if n != 1:
            print("  DRIFTED %s (anchor found %d times)"
                  % (os.path.basename(path), n))
            continue
        open(path, "w").write(s.replace(old, new))
        applied += 1
    print("  message pump: %d edits applied, %d already done" % (applied, skipped))


if __name__ == "__main__":
    main()
