#!/usr/bin/env python3
"""Add OS_HAIKU to Chromium's platform detection.

build/build_config.h is the root of every platform decision in the tree: it
turns a compiler predefine into OS_* macros, which BUILDFLAG(IS_*) reads.
Nothing else in the port can be written until Haiku exists here.
"""
import sys

p = sys.argv[1]
s = open(p).read()
changed = []

# 1. Recognise the platform at all. __HAIKU__ is Haiku's own predefine.
old = """#elif defined(__MVS__)
#define OS_ZOS 1
#else
#error Please add support for your platform in build/build_config.h
#endif"""
new = """#elif defined(__MVS__)
#define OS_ZOS 1
#elif defined(__HAIKU__)
#define OS_HAIKU 1
#else
#error Please add support for your platform in build/build_config.h
#endif"""
if "OS_HAIKU 1" not in s:
    assert s.count(old) == 1, "OS detection chain does not look as expected"
    s = s.replace(old, new)
    changed.append("OS detection")

# 2. Haiku is POSIX-ish: it has pthreads, mmap, unix sockets, dlopen. The
#    places that are not POSIX -- no fork+exec sandbox, no /proc -- are dealt
#    with individually rather than by pretending it is not POSIX at all,
#    because ~500 IS_POSIX branches is far more code than the handful of
#    genuine differences.
old = """    defined(OS_OPENBSD) || defined(OS_QNX) || defined(OS_SOLARIS) || \\
    defined(OS_ZOS)
#define OS_POSIX 1
#endif"""
new = """    defined(OS_OPENBSD) || defined(OS_QNX) || defined(OS_SOLARIS) || \\
    defined(OS_ZOS) || defined(OS_HAIKU)
#define OS_POSIX 1
#endif"""
if "defined(OS_ZOS) || defined(OS_HAIKU)" not in s:
    assert s.count(old) == 1, "OS_POSIX list does not look as expected"
    s = s.replace(old, new)
    changed.append("OS_POSIX")

# 3. The BUILDFLAG plumbing, kept in the alphabetical order the file uses.
old = """#if defined(OS_FUCHSIA)
#define BUILDFLAG_INTERNAL_IS_FUCHSIA() (1)
#else
#define BUILDFLAG_INTERNAL_IS_FUCHSIA() (0)
#endif"""
new = """#if defined(OS_FUCHSIA)
#define BUILDFLAG_INTERNAL_IS_FUCHSIA() (1)
#else
#define BUILDFLAG_INTERNAL_IS_FUCHSIA() (0)
#endif

#if defined(OS_HAIKU)
#define BUILDFLAG_INTERNAL_IS_HAIKU() (1)
#else
#define BUILDFLAG_INTERNAL_IS_HAIKU() (0)
#endif"""
if "BUILDFLAG_INTERNAL_IS_HAIKU" not in s:
    assert s.count(old) == 1, "BUILDFLAG block does not look as expected"
    s = s.replace(old, new)
    changed.append("BUILDFLAG(IS_HAIKU)")

if not changed:
    print("  build_config.h: already patched")
else:
    open(p, "w").write(s)
    print("  build_config.h: " + ", ".join(changed))
