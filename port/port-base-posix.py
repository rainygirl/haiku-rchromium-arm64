#!/usr/bin/env python3
"""Make //base's POSIX files build on Haiku.

With the epoll wall down the POSIX implementation files behind it become
reachable, and they reach for Linux facilities Haiku does not have. Most are
already guarded at the point of use and it is only the unconditional
`#include` at the top of the file that fails; those get the same condition as
their callers. The rest need Haiku's own answer, or a stub where Haiku has
none and the caller can do without one.

`__HAIKU__` rather than `BUILDFLAG(IS_HAIKU)` for the includes: they sit above
the point where build_config.h has been read.
"""
import os
import sys

# Every syscall() in these is already inside a Linux/Android/ChromeOS guard;
# only the include is unconditional.
SYSCALL_INCLUDE_ONLY = [
    "base/rand_util_posix.cc",
    "base/process/launch_posix.cc",
    "base/debug/stack_trace_posix.cc",
    "base/memory/platform_shared_memory_region_posix.cc",
]

EDITS = [(rel,
          "#include <sys/syscall.h>\n",
          "#if !defined(__HAIKU__)\n"
          "#include <sys/syscall.h>\n"
          "#endif\n")
         for rel in SYSCALL_INCLUDE_ONLY]

EDITS += [
    # Nice values. Haiku has setpriority() but neither RLIMIT_NICE nor NZERO:
    # there is no rlimit governing how far a thread may lower its niceness, so
    # there is nothing to consult and no way to raise it back afterwards.
    ("base/posix/can_lower_nice_to.cc",
     "bool CanLowerNiceTo(int nice_value) {\n",
     "bool CanLowerNiceTo(int nice_value) {\n"
     "#if BUILDFLAG(IS_HAIKU)\n"
     "  // Haiku has no RLIMIT_NICE to consult.\n"
     "  return false;\n"
     "#else\n"),

    ("base/posix/can_lower_nice_to.cc",
     "  return nice_value >= lowest_nice_allowed;\n}\n",
     "  return nice_value >= lowest_nice_allowed;\n"
     "#endif  // BUILDFLAG(IS_HAIKU)\n"
     "}\n"),

    # ftruncate64 is a glibc spelling. Haiku's ftruncate already takes a
    # 64-bit off_t, so it is the same function under the standard name --
    # which is what the BSD and Apple branch just above already uses.
    ("base/files/file_posix.cc",
     "#if BUILDFLAG(IS_BSD) || BUILDFLAG(IS_APPLE) || BUILDFLAG(IS_FUCHSIA)\n",
     "#if BUILDFLAG(IS_BSD) || BUILDFLAG(IS_APPLE) || BUILDFLAG(IS_FUCHSIA) || \\\n"
     "    BUILDFLAG(IS_HAIKU)\n"),

    # futimes vs futimens. Haiku has futimens and not futimes; the file
    # already prefers futimens when __USE_XOPEN2K8 says it is available, which
    # is a glibc macro Haiku does not define.
    ("base/files/file_posix.cc",
     "#ifdef __USE_XOPEN2K8\n",
     "#if defined(__USE_XOPEN2K8) || defined(__HAIKU__)\n"),

    # PF_X is an ELF program-header flag from <elf.h>, which Haiku does not
    # ship. The profiler's module cache walks program headers to find the
    # executable segment; without the constant it cannot. Define it -- the
    # value is fixed by the ELF specification, not by any platform.
    ("base/profiler/module_cache_posix.cc",
     "size_t GetLastExecutableOffset(const void* module_addr) {\n",
     "#if defined(__HAIKU__) && !defined(PF_X)\n"
     "// From the ELF specification; Haiku ships no <elf.h> defining it.\n"
     "#define PF_X 0x1\n"
     "#endif\n"
     "\n"
     "size_t GetLastExecutableOffset(const void* module_addr) {\n"),

    # The per-platform guess at the system's file-descriptor limit, used only
    # as a fallback when getrlimit() fails.
    ("base/process/process_metrics_posix.cc",
     "#elif BUILDFLAG(IS_SOLARIS)\nstatic const rlim_t kSystemDefaultMaxFds = 8192;\n",
     "#elif BUILDFLAG(IS_HAIKU)\nstatic const rlim_t kSystemDefaultMaxFds = 8192;\n"
     "#elif BUILDFLAG(IS_SOLARIS)\nstatic const rlim_t kSystemDefaultMaxFds = 8192;\n"),

    # /proc/self/fd. Haiku mounts the same thing at /dev/fd, as Solaris does.
    ("base/process/launch_posix.cc",
     '#elif BUILDFLAG(IS_SOLARIS)\nstatic const char kFDDir[] = "/dev/fd";\n',
     '#elif BUILDFLAG(IS_SOLARIS) || BUILDFLAG(IS_HAIKU)\n'
     'static const char kFDDir[] = "/dev/fd";\n'),

    # Drive characteristics come from /sys/dev/block on Linux. Haiku has no
    # equivalent, so answer the way Android and Fuchsia do: nothing known.
    ("base/files/drive_info_posix.cc",
     "#if BUILDFLAG(IS_ANDROID) || BUILDFLAG(IS_FUCHSIA)\n"
     "  drive_info.has_seek_penalty = false;\n"
     "  return drive_info;\n",
     "#if BUILDFLAG(IS_ANDROID) || BUILDFLAG(IS_FUCHSIA) || BUILDFLAG(IS_HAIKU)\n"
     "  drive_info.has_seek_penalty = false;\n"
     "  return drive_info;\n"),

    # The shared-memory error codes the POSIX implementation reports are
    # declared only for Linux and ChromeOS, though the code that raises them
    # is compiled for every POSIX platform.
    ("base/memory/platform_shared_memory_region.h",
     "#if BUILDFLAG(IS_CHROMEOS) || BUILDFLAG(IS_LINUX)\n"
     "    kFcntlFailed,\n",
     "#if BUILDFLAG(IS_CHROMEOS) || BUILDFLAG(IS_LINUX) || BUILDFLAG(IS_HAIKU)\n"
     "    kFcntlFailed,\n"),

    # Thread ids. reinterpret_cast from a pointer to int64_t is fine on Linux,
    # where pthread_t is an integer; on Haiku it is a pointer to a struct and
    # PlatformThreadId is constructed from Haiku's own thread_id instead --
    # the small integer its tools display.
    ("base/threading/platform_thread_posix.cc",
     "#elif BUILDFLAG(IS_POSIX) && !BUILDFLAG(IS_AIX)\n"
     "  return PlatformThreadId(reinterpret_cast<int64_t>(pthread_self()));\n",
     "#elif BUILDFLAG(IS_HAIKU)\n"
     "  return PlatformThreadId(static_cast<int64_t>(find_thread(nullptr)));\n"
     "#elif BUILDFLAG(IS_POSIX) && !BUILDFLAG(IS_AIX)\n"
     "  return PlatformThreadId(reinterpret_cast<int64_t>(pthread_self()));\n"),

    ("base/threading/platform_thread_posix.cc",
     "#include <sys/resource.h>\n",
     "#include <sys/resource.h>\n"
     "#if defined(__HAIKU__)\n"
     "#include <OS.h>  // find_thread\n"
     "#endif\n"),

    # mincore() reports which pages of a mapping are resident. Haiku has no
    # equivalent, so CountResidentBytes has nothing to count -- the branch
    # taken is the one that reports failure, which callers already handle.
    ("base/trace_event/process_memory_dump.cc",
     "#elif BUILDFLAG(IS_POSIX)\n"
     "    int error_counter = 0;\n",
     "#elif BUILDFLAG(IS_HAIKU)\n"
     "    // No mincore() here, so residency cannot be measured. Report the\n"
     "    // failure the function already knows how to report; the locals the\n"
     "    // other branches share stay used, so nothing goes unused-warning.\n"
     "    failure = true;\n"
     "    for (size_t i = 0; i < page_count; i++) {\n"
     "      accumulate_page_if_resident(i, false);\n"
     "    }\n"
     "#elif BUILDFLAG(IS_POSIX)\n"
     "    int error_counter = 0;\n"),

    # CLOCK_MONOTONIC_COARSE is a Linux extension; the plain monotonic clock
    # is the fallback this code already uses elsewhere.
    ("base/time/time_now_posix.cc",
     "  return TimeTicks() + Microseconds(ClockNow(CLOCK_MONOTONIC_COARSE));\n",
     "#if defined(CLOCK_MONOTONIC_COARSE)\n"
     "  return TimeTicks() + Microseconds(ClockNow(CLOCK_MONOTONIC_COARSE));\n"
     "#else\n"
     "  // No coarse clock here; the plain monotonic one is correct, just\n"
     "  // marginally more expensive to read.\n"
     "  return TimeTicks() + Microseconds(ClockNow(CLOCK_MONOTONIC));\n"
     "#endif\n"),

    # SO_PASSCRED and SCM_CREDENTIALS are the Linux way of passing a peer's
    # credentials over a unix socket. Haiku has neither, the same as macOS,
    # which this file already handles.
    ("base/posix/unix_domain_socket.cc",
     "#if !BUILDFLAG(IS_APPLE)\n"
     "  const int enable = 1;\n",
     "#if !BUILDFLAG(IS_APPLE) && !BUILDFLAG(IS_HAIKU)\n"
     "  const int enable = 1;\n"),

    ("base/posix/unix_domain_socket.cc",
     "#if !BUILDFLAG(IS_APPLE)\n"
     "      // macOS does not support SCM_CREDENTIALS.\n",
     "#if !BUILDFLAG(IS_APPLE) && !BUILDFLAG(IS_HAIKU)\n"
     "      // Neither macOS nor Haiku supports SCM_CREDENTIALS.\n"),

    # statvfs fields. Haiku declares f_bavail and f_blocks as signed
    # fsblkcnt_t; multiplying them promotes to unsigned and -Wsign-conversion
    # rejects it. The values are non-negative by definition.
    ("base/system/sys_info_posix.cc",
     "          : base::saturated_cast<int64_t>(stats.f_bavail * stats.f_frsize);\n",
     "          : base::saturated_cast<int64_t>(\n"
     "                static_cast<uint64_t>(stats.f_bavail) *\n"
     "                static_cast<uint64_t>(stats.f_frsize));\n"),

    ("base/system/sys_info_posix.cc",
     "          : base::saturated_cast<int64_t>(stats.f_blocks * stats.f_frsize);\n",
     "          : base::saturated_cast<int64_t>(\n"
     "                static_cast<uint64_t>(stats.f_blocks) *\n"
     "                static_cast<uint64_t>(stats.f_frsize));\n"),

    # PlatformThreadId is constructed from whatever the platform's native id
    # is; on Haiku that is thread_id, a 32-bit int, and the int64_t cast has
    # no matching constructor.
    ("base/threading/platform_thread_posix.cc",
     "#elif BUILDFLAG(IS_HAIKU)\n"
     "  return PlatformThreadId(static_cast<int64_t>(find_thread(nullptr)));\n",
     "#elif BUILDFLAG(IS_HAIKU)\n"
     "  return PlatformThreadId(find_thread(nullptr));\n"),

    # Malloc accounting. Haiku's allocator exposes no mallinfo-style figure,
    # so report nothing rather than a wrong number, as Fuchsia does.
    ("base/process/process_metrics_posix.cc",
     "#elif BUILDFLAG(IS_FUCHSIA)\n"
     "  // TODO(fuchsia): Not currently exposed. https://crbug.com/735087.\n"
     "  return 0;\n"
     "#endif\n",
     "#elif BUILDFLAG(IS_FUCHSIA) || BUILDFLAG(IS_HAIKU)\n"
     "  // Not exposed by either allocator.\n"
     "  return 0;\n"
     "#endif\n"),

    # msg_controllen and cmsg_len are 32-bit on Haiku as they are on macOS,
    # so the same narrowing casts apply.
    ("base/posix/unix_domain_socket.cc",
     "#if BUILDFLAG(IS_APPLE)\n"
     "    msg.msg_controllen = checked_cast<socklen_t>(control_len);\n",
     "#if BUILDFLAG(IS_APPLE) || BUILDFLAG(IS_HAIKU)\n"
     "    msg.msg_controllen = checked_cast<socklen_t>(control_len);\n"),

    ("base/posix/unix_domain_socket.cc",
     "#if BUILDFLAG(IS_APPLE)\n"
     "    cmsg->cmsg_len = checked_cast<u_int>(CMSG_LEN(sizeof(int) * fds.size()));\n",
     "#if BUILDFLAG(IS_APPLE) || BUILDFLAG(IS_HAIKU)\n"
     "    cmsg->cmsg_len = checked_cast<u_int>(CMSG_LEN(sizeof(int) * fds.size()));\n"),
]


def main(src):
    applied = drifted = skipped = 0
    for rel, old, new in EDITS:
        p = os.path.join(src, rel)
        if not os.path.exists(p):
            print("  MISSING %s" % rel)
            continue
        s = open(p).read()
        if new in s:
            skipped += 1
            continue
        n = s.count(old)
        if n != 1:
            print("  DRIFTED %s (anchor found %d times)" % (rel, n))
            drifted += 1
            continue
        open(p, "w").write(s.replace(old, new))
        applied += 1
    print("  base posix: %d applied, %d already done, %d drifted"
          % (applied, skipped, drifted))


if __name__ == "__main__":
    main(sys.argv[1])
