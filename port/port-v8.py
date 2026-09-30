#!/usr/bin/env python3
"""Make //v8 build on Haiku.

V8 keeps its own operating-system detection, separate from build_config.h,
and everything below it -- semaphores, clocks, the sampler, sys-info --
branches on V8_OS_*. With no Haiku branch those all fall off the end of
their #if chains, which is why a single missing macro produced hundreds of
unrelated-looking errors. Teach v8config.h about Haiku and nearly all of
them resolve into the existing V8_OS_POSIX paths, which are correct here.

What remains is the handful of things POSIX does not cover: the per-OS
platform file, and one header Haiku does not ship.
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

EDITS = [
    # The OS detection itself. Haiku is POSIX for every purpose V8 cares
    # about here: sem_t semaphores, clock_gettime, sysconf, getrlimit.
    ("v8/include/v8config.h",
     "#elif defined(_WIN32)\n"
     "# define V8_OS_WIN 1\n"
     "# define V8_OS_STRING \"windows\"\n",
     "#elif defined(__HAIKU__)\n"
     "# define V8_OS_HAIKU 1\n"
     "# define V8_OS_POSIX 1\n"
     "# define V8_OS_STRING \"haiku\"\n"
     "\n"
     "#elif defined(_WIN32)\n"
     "# define V8_OS_WIN 1\n"
     "# define V8_OS_STRING \"windows\"\n"),

    ("v8/include/v8config.h",
     "//  V8_OS_OPENBSD       - OpenBSD\n",
     "//  V8_OS_HAIKU         - Haiku\n"
     "//  V8_OS_OPENBSD       - OpenBSD\n"),

    # The target-OS half of the same thing. V8_HAVE_TARGET_OS is unset in
    # this build, so the target follows the detected host; the list below is
    # the "a target was named without the flag" guard, and Haiku belongs in
    # it for the same reason every other OS does.
    ("v8/include/v8config.h",
     "# if defined(V8_TARGET_OS_ANDROID) \\\n"
     "  || defined(V8_TARGET_OS_FUCHSIA) \\\n"
     "  || defined(V8_TARGET_OS_IOS) \\\n"
     "  || defined(V8_TARGET_OS_TVOS) \\\n"
     "  || defined(V8_TARGET_OS_LINUX) \\\n"
     "  || defined(V8_TARGET_OS_MACOS) \\\n"
     "  || defined(V8_TARGET_OS_WIN) \\\n"
     "  || defined(V8_TARGET_OS_CHROMEOS)\n"
     "#  error A target OS is defined but V8_HAVE_TARGET_OS is unset.\n",
     "# if defined(V8_TARGET_OS_ANDROID) \\\n"
     "  || defined(V8_TARGET_OS_FUCHSIA) \\\n"
     "  || defined(V8_TARGET_OS_HAIKU) \\\n"
     "  || defined(V8_TARGET_OS_IOS) \\\n"
     "  || defined(V8_TARGET_OS_TVOS) \\\n"
     "  || defined(V8_TARGET_OS_LINUX) \\\n"
     "  || defined(V8_TARGET_OS_MACOS) \\\n"
     "  || defined(V8_TARGET_OS_WIN) \\\n"
     "  || defined(V8_TARGET_OS_CHROMEOS)\n"
     "#  error A target OS is defined but V8_HAVE_TARGET_OS is unset.\n"),

    ("v8/include/v8config.h",
     "#ifdef V8_OS_WIN\n"
     "# define V8_TARGET_OS_WIN\n"
     "#endif\n",
     "#ifdef V8_OS_HAIKU\n"
     "# define V8_TARGET_OS_HAIKU\n"
     "#endif\n"
     "\n"
     "#ifdef V8_OS_WIN\n"
     "# define V8_TARGET_OS_WIN\n"
     "#endif\n"),

    ("v8/include/v8config.h",
     "#elif defined(V8_TARGET_OS_LINUX)\n"
     "# define V8_TARGET_OS_STRING \"linux\"\n",
     "#elif defined(V8_TARGET_OS_HAIKU)\n"
     "# define V8_TARGET_OS_STRING \"haiku\"\n"
     "#elif defined(V8_TARGET_OS_LINUX)\n"
     "# define V8_TARGET_OS_STRING \"linux\"\n"),

    # Haiku ships no <sys/syscall.h>: it has no stable syscall numbers to
    # expose, and nothing in the POSIX paths below actually calls syscall().
    ("v8/src/base/platform/platform-posix.cc",
     "#if !defined(_AIX) && !defined(V8_OS_FUCHSIA) && !V8_OS_ZOS\n"
     "#include <sys/syscall.h>\n"
     "#endif\n",
     "#if !defined(_AIX) && !defined(V8_OS_FUCHSIA) && !V8_OS_ZOS && \\\n"
     "    !defined(V8_OS_HAIKU)\n"
     "// Haiku exposes no stable syscall numbers, and none of the POSIX paths\n"
     "// below reach for syscall() anyway.\n"
     "#include <sys/syscall.h>\n"
     "#endif\n"),

    # Decommitting a page must not be able to kill the browser.
    #
    # BoundedPageAllocator::FreePages does
    #   success = page_allocator_->DecommitPages(...); CHECK(success);
    # when the allocator promises zero-initialized pages, so a failure here is
    # fatal -- V8_Fatal("Check failed: success."), which is how R Twitter kept
    # going away a minute or two into x.com.
    #
    # DecommitPages is an mmap(MAP_FIXED, PROT_NONE) over a live mapping, and
    # on Haiku that is asking the kernel to delete the area under the range
    # and build a new one. Two things make it fail where Linux would not:
    # MAP_NORESERVE is not in the flags, and Haiku commits memory for an
    # anonymous mapping whatever its protection ("don't commit memory" is
    # exactly what its MAP_NORESERVE means); and the new area has to be
    # carved out of an address space that a long-running renderer has
    # thoroughly fragmented. Either way it comes back ENOMEM.
    #
    # So: ask for no commitment, and if the mapping still cannot be made, do
    # by hand what it was for. The caller does not need a new mapping, it
    # needs the range to stay reserved and to read back as zero.
    ("v8/src/base/platform/platform-posix.cc",
     "  void* ret = mmap(address, size, PROT_NONE,\n"
     "                   MAP_FIXED | MAP_ANONYMOUS | MAP_PRIVATE, -1, 0);\n"
     "  if (V8_UNLIKELY(ret == MAP_FAILED)) {\n"
     "    // Decommitting pages can fail if the limit of VMAs is exceeded.\n"
     "    CHECK_EQ(ENOMEM, errno);\n"
     "    return false;\n"
     "  }\n",
     "  int decommit_flags = MAP_FIXED | MAP_ANONYMOUS | MAP_PRIVATE;\n"
     "#ifdef V8_OS_HAIKU\n"
     "  // The range is about to hold nothing, so do not make the kernel find\n"
     "  // memory for it. Haiku's MAP_NORESERVE is documented as \"don't commit\n"
     "  // memory\", which is the whole intent here.\n"
     "  decommit_flags |= MAP_NORESERVE;\n"
     "#endif\n"
     "  void* ret = mmap(address, size, PROT_NONE, decommit_flags, -1, 0);\n"
     "  if (V8_UNLIKELY(ret == MAP_FAILED)) {\n"
     "    // Decommitting pages can fail if the limit of VMAs is exceeded.\n"
     "    CHECK_EQ(ENOMEM, errno);\n"
     "#ifdef V8_OS_HAIKU\n"
     "    // Haiku cannot always replace the mapping: MAP_FIXED over a live\n"
     "    // range means deleting one area and creating another, and in a\n"
     "    // fragmented address space the new one is what runs out. The\n"
     "    // callers of this function do not need a new mapping; they need the\n"
     "    // range to stay reserved and to read back as zero. Do that in\n"
     "    // place. It leaves the pages resident, which is why it is the\n"
     "    // fallback and not the first choice -- but a resident page costs\n"
     "    // less than the CHECK(success) in BoundedPageAllocator::FreePages,\n"
     "    // which ends the process.\n"
     "    if (mprotect(address, size, PROT_READ | PROT_WRITE) == 0) {\n"
     "      memset(address, 0, size);\n"
     "      // Taking the permissions away again is what the mmap would have\n"
     "      // done. If Haiku cannot split the area for it, zeroed and\n"
     "      // writable still satisfies every caller.\n"
     "      mprotect(address, size, PROT_NONE);\n"
     "      static bool reported = false;\n"
     "      if (!reported) {\n"
     "        reported = true;\n"
     "        fprintf(stderr, \"[RCH] DecommitPages: mmap came back ENOMEM; \"\n"
     "                \"zeroing in place instead\\n\");\n"
     "      }\n"
     "      return true;\n"
     "    }\n"
     "#endif\n"
     "    return false;\n"
     "  }\n"),

    # Select the platform file. This mirrors the aix branch: the POSIX
    # backtrace implementation plus one OS-specific source.
    ("v8/BUILD.gn",
     "  } else if (current_os == \"aix\") {\n"
     "    sources += [\n"
     "      \"src/base/debug/stack_trace_posix.cc\",\n"
     "      \"src/base/platform/platform-aix.cc\",\n"
     "    ]\n",
     "  } else if (is_haiku) {\n"
     "    sources += [\n"
     "      \"src/base/debug/stack_trace_posix.cc\",\n"
     "      \"src/base/platform/platform-haiku.cc\",\n"
     "    ]\n"
     "  } else if (current_os == \"aix\") {\n"
     "    sources += [\n"
     "      \"src/base/debug/stack_trace_posix.cc\",\n"
     "      \"src/base/platform/platform-aix.cc\",\n"
     "    ]\n"),

    # Give Haiku a V8_TARGET_OS_* the same way every supported OS gets one.
    #
    # This matters more than it looks. With target_os unrecognised,
    # V8_HAVE_TARGET_OS never gets set, so v8config.h falls back to detecting
    # the *host* -- and the host toolchain that builds mksnapshot is Linux.
    # The fallback defines V8_TARGET_OS_LINUX with an empty body, whereas the
    # GN path defines it via -D, which the preprocessor gives the value 1.
    # Code written as `#if V8_TARGET_OS_LINUX` then sees an empty expression
    # and fails to parse. Naming Haiku here keeps the define on the command
    # line, where it has a value, and leaves V8_TARGET_OS_LINUX undefined --
    # which is what the mksnapshot build should see, since it is producing a
    # snapshot for Haiku.
    ("v8/BUILD.gn",
     "  \"V8_TARGET_OS_IOS\",\n"
     "  \"V8_TARGET_OS_LINUX\",\n",
     "  \"V8_TARGET_OS_HAIKU\",\n"
     "  \"V8_TARGET_OS_IOS\",\n"
     "  \"V8_TARGET_OS_LINUX\",\n"),

    ("v8/BUILD.gn",
     "} else if (target_os == \"linux\") {\n"
     "  enabled_external_v8_defines += [ \"V8_HAVE_TARGET_OS\" ]\n"
     "  enabled_external_v8_defines += [ \"V8_TARGET_OS_LINUX\" ]\n",
     "} else if (target_os == \"haiku\") {\n"
     "  enabled_external_v8_defines += [ \"V8_HAVE_TARGET_OS\" ]\n"
     "  enabled_external_v8_defines += [ \"V8_TARGET_OS_HAIKU\" ]\n"
     "} else if (target_os == \"linux\") {\n"
     "  enabled_external_v8_defines += [ \"V8_HAVE_TARGET_OS\" ]\n"
     "  enabled_external_v8_defines += [ \"V8_TARGET_OS_LINUX\" ]\n"),

    # Haiku ships no <execinfo.h>, so HAVE_EXECINFO_H is 0 and the whole
    # demangling helper is compiled out -- leaving these two constants, which
    # nothing else reads, to trip -Wunused-const-variable. They belong inside
    # the guard with their only user.
    ("v8/src/base/debug/stack_trace_posix.cc",
     "// The prefix used for mangled symbols, per the Itanium C++ ABI:\n"
     "// http://www.codesourcery.com/cxx-abi/abi.html#mangling\n"
     "const char kMangledSymbolPrefix[] = \"_Z\";\n"
     "\n"
     "// Characters that can be used for symbols, generated by Ruby:\n"
     "// ((\'a\'..\'z\').to_a+(\'A\'..\'Z\').to_a+(\'0\'..\'9\').to_a + [\'_\']).join\n"
     "const char kSymbolCharacters[] =\n"
     "    \"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_\";\n"
     "\n"
     "#if HAVE_EXECINFO_H\n",
     "#if HAVE_EXECINFO_H\n"
     "// The prefix used for mangled symbols, per the Itanium C++ ABI:\n"
     "// http://www.codesourcery.com/cxx-abi/abi.html#mangling\n"
     "const char kMangledSymbolPrefix[] = \"_Z\";\n"
     "\n"
     "// Characters that can be used for symbols, generated by Ruby:\n"
     "// ((\'a\'..\'z\').to_a+(\'A\'..\'Z\').to_a+(\'0\'..\'9\').to_a + [\'_\']).join\n"
     "const char kSymbolCharacters[] =\n"
     "    \"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_\";\n"
     "\n"),

    # The other half of the target-OS check. This is the branch taken now that
    # V8_HAVE_TARGET_OS is set from BUILD.gn: it asserts the target named is
    # one v8config.h knows about.
    ("v8/include/v8config.h",
     "# if !defined(V8_TARGET_OS_ANDROID) \\\n"
     "  && !defined(V8_TARGET_OS_FUCHSIA) \\\n"
     "  && !defined(V8_TARGET_OS_IOS) \\\n",
     "# if !defined(V8_TARGET_OS_ANDROID) \\\n"
     "  && !defined(V8_TARGET_OS_FUCHSIA) \\\n"
     "  && !defined(V8_TARGET_OS_HAIKU) \\\n"
     "  && !defined(V8_TARGET_OS_IOS) \\\n"),

    # llvm-libc, reached through v8/src/base/ieee754.cc.
    #
    # The shift only makes sense when narrowing, and the guard says so -- but
    # it is a runtime if, so the widening instantiations (float -> Float128,
    # _Float16 -> double) still compile the shift, with a negative count.
    # arm64 has native _Float16, so those instantiations exist here where they
    # may not on other targets. if constexpr discards the branch instead of
    # merely skipping it, which is what the guard meant all along.
    ("third_party/llvm-libc/src/src/__support/FPUtil/cast.h",
     "        if (InFPBits::FRACTION_LEN > OutFPBits::FRACTION_LEN)\n",
     "        if constexpr (InFPBits::FRACTION_LEN > OutFPBits::FRACTION_LEN)\n"),

    # Same as platform-posix.cc: the include is there for other platforms'
    # sake, and nothing in this file calls syscall().
    ("v8/src/libsampler/sampler.cc",
     "#if !V8_OS_QNX && !V8_OS_AIX && !V8_OS_ZOS\n"
     "#include <sys/syscall.h>\n"
     "#endif\n",
     "#if !V8_OS_QNX && !V8_OS_AIX && !V8_OS_ZOS && !V8_OS_HAIKU\n"
     "#include <sys/syscall.h>\n"
     "#endif\n"),

    # Haiku is in the same position as OpenBSD here: no <ucontext.h>, with
    # ucontext_t declared in <signal.h> instead. Unlike OpenBSD it does have
    # uc_mcontext, so only the include needs skipping.
    ("v8/src/libsampler/sampler.cc",
     "#elif !V8_OS_OPENBSD\n"
     "#include <ucontext.h>\n"
     "#endif\n",
     "#elif !V8_OS_OPENBSD && !V8_OS_HAIKU\n"
     "// Haiku declares ucontext_t in <signal.h> and ships no <ucontext.h>.\n"
     "#include <ucontext.h>\n"
     "#endif\n"),

    # Pull the sampled registers out of Haiku's mcontext_t, which is
    # struct vregs (headers/posix/arch/arm64/signal.h): x[] holds x0..x29,
    # while x30 and the stack pointer are named fields, and elr holds the
    # address the exception returns to -- that is the interrupted pc.
    ("v8/src/libsampler/sampler.cc",
     "#if V8_OS_LINUX\n"
     "#if V8_HOST_ARCH_IA32\n",
     "#if V8_OS_HAIKU\n"
     "#if V8_HOST_ARCH_ARM64\n"
     "  state->pc = reinterpret_cast<void*>(mcontext.elr);\n"
     "  state->sp = reinterpret_cast<void*>(mcontext.sp);\n"
     "  // FP is an alias for x29, LR for x30 -- which Haiku names separately.\n"
     "  state->fp = reinterpret_cast<void*>(mcontext.x[29]);\n"
     "  state->lr = reinterpret_cast<void*>(mcontext.lr);\n"
     "#else\n"
     "#error Unsupported Haiku architecture for the sampler.\n"
     "#endif\n"
     "#elif V8_OS_LINUX\n"
     "#if V8_HOST_ARCH_IA32\n"),

    # TLS model. V8 picks "local-exec" for everything that is neither Windows
    # nor Android, which is right when the binary is an ET_EXEC. Haiku links
    # every executable as ET_DYN, so lld rejects the local-exec relocations
    # with "cannot be used with -shared". "initial-exec" is the next fastest
    # model and is what Windows already uses for the same reason: the variable
    # still lives in the initial TLS block, only addressed through the GOT.
    ("v8/src/common/thread-local-storage.h",
     "#elif defined(V8_TARGET_OS_ANDROID)\n"
     "#define V8_TLS_MODEL \"local-dynamic\"\n",
     "#elif defined(V8_TARGET_OS_ANDROID) || defined(V8_TARGET_OS_HAIKU)\n"
     "#define V8_TLS_MODEL \"local-dynamic\"\n"),
]

COPIES = [
    ("v8/platform-haiku.cc", "v8/src/base/platform/platform-haiku.cc"),
]


def main(src):
    applied = skipped = drifted = 0
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
        open(p, "w").write(s.replace(old, new, 1))
        applied += 1

    copied = 0
    for rel_src, rel_dst in COPIES:
        s = os.path.join(HERE, "files", rel_src)
        d = os.path.join(src, rel_dst)
        if not os.path.exists(s):
            print("  MISSING source %s" % rel_src)
            continue
        if not (os.path.exists(d) and open(d).read() == open(s).read()):
            shutil.copyfile(s, d)
            copied += 1

    print("  v8: %d applied, %d already done, %d drifted, %d copied"
          % (applied, skipped, drifted, copied))


if __name__ == "__main__":
    main(sys.argv[1])
