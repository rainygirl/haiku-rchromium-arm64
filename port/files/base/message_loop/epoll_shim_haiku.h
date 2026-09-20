// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef BASE_MESSAGE_LOOP_EPOLL_SHIM_HAIKU_H_
#define BASE_MESSAGE_LOOP_EPOLL_SHIM_HAIKU_H_

// Haiku has poll() but neither epoll nor kqueue, and Chromium removed its
// libevent pump, so message_pump_for_io.h maps every POSIX platform to
// MessagePumpEpoll.
//
// That pump already contains a complete poll() implementation --
// GetEventsPoll(), guarded by the kUsePollForMessagePumpEpoll feature, added
// for Android's scheduler behaviour rather than for portability. On that path
// epoll_event is used only as a plain struct to carry results, and the EPOLL*
// values only as bit flags mapped to and from the POLL* ones.
//
// So all Haiku needs is the type and the constants. The pump is compiled with
// its epoll_create/epoll_ctl/epoll_wait calls left out and the poll path
// forced on; see the changes to message_pump_epoll.{h,cc}.
//
// The bit values are the Linux ones. Nothing here is passed to a kernel: they
// are only compared against each other and against the kEpollToPollEvents
// table, so what matters is that they are distinct.

#include <fcntl.h>
#include <netinet/in.h>
#include <poll.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
#include <cstdint>

enum {
  EPOLLIN = 0x001,
  EPOLLPRI = 0x002,
  EPOLLOUT = 0x004,
  EPOLLERR = 0x008,
  EPOLLHUP = 0x010,
  EPOLLRDHUP = 0x2000,
  EPOLLONESHOT = 1u << 30,
};

// Haiku has no POLLRDHUP. A peer closing its end of a socket shows up as
// POLLHUP there, which the pump already handles, so mapping EPOLLRDHUP onto
// nothing loses no events.
#if !defined(POLLRDHUP)
#define POLLRDHUP 0
#endif

typedef union epoll_data {
  void* ptr;
  int fd;
  uint32_t u32;
  uint64_t u64;
} epoll_data_t;

struct epoll_event {
  uint32_t events;
  epoll_data_t data;
};

// eventfd(). Haiku has none, and the pump wants one file descriptor it can
// both write a token to and read it back from -- a pipe gives two. A UDP
// socket connected to its own address is one descriptor with exactly that
// behaviour: an 8-byte datagram written to it becomes an 8-byte datagram
// readable from it, and poll() reports POLLIN while any is queued.
//
// The one difference from a real eventfd is that the token does not
// accumulate into a counter: two writes queue two datagrams and one read
// drains one of them, so the pump may wake once more than it strictly needs
// to. A spurious wake-up is something it already handles.
#define EFD_NONBLOCK O_NONBLOCK

static inline int eventfd(unsigned int initval, int flags) {
  int fd = socket(AF_INET, SOCK_DGRAM, 0);
  if (fd < 0) {
    return -1;
  }

  struct sockaddr_in addr;
  memset(&addr, 0, sizeof(addr));
  addr.sin_family = AF_INET;
  addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
  addr.sin_port = 0;  // Any free port.

  socklen_t len = sizeof(addr);
  if (bind(fd, (struct sockaddr*)&addr, sizeof(addr)) != 0 ||
      getsockname(fd, (struct sockaddr*)&addr, &len) != 0 ||
      connect(fd, (struct sockaddr*)&addr, len) != 0) {
    close(fd);
    return -1;
  }

  if ((flags & EFD_NONBLOCK) != 0) {
    int file_flags = fcntl(fd, F_GETFL, 0);
    if (file_flags < 0 || fcntl(fd, F_SETFL, file_flags | O_NONBLOCK) != 0) {
      close(fd);
      return -1;
    }
  }

  return fd;
}

#endif  // BASE_MESSAGE_LOOP_EPOLL_SHIM_HAIKU_H_
