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
