#!/usr/bin/env python3
"""Add Haiku to Chromium's platform lists.

Most of a new-OS port's gn work is this: .gni files that enumerate the
platforms a feature supports as `is_linux || is_mac || is_win`, and a
BUILD.gn somewhere that asserts the feature is on. Haiku is a desktop system,
so in nearly every case the answer is to add it to the desktop list.

Each entry is a (file, old, new) triple, applied only if `old` occurs exactly
once. Anything that has drifted upstream fails loudly rather than silently
patching the wrong thing.
"""
import sys

EDITS = [
    # Supervision for Family Link users. //chrome/test asserts this is on for
    # any platform that has //chrome at all.
    ("components/supervised_user/buildflags.gni",
     "      is_android || is_chromeos || is_ios || is_linux || is_mac || is_win",
     "      is_android || is_chromeos || is_ios || is_linux || is_mac ||\n"
     "      is_win || is_haiku"),

    # C++ modules: where the system headers sit under the sysroot. Haiku
    # puts them in boot/system/develop/headers rather than usr/include.
    ("build/modules/BUILD.gn",
     '  } else if (is_fuchsia) {\n'
     '    root_include_dir = "include"\n',
     '  } else if (is_haiku) {\n'
     '    root_include_dir = "boot/system/develop/headers"\n'
     '  } else if (is_fuchsia) {\n'
     '    root_include_dir = "include"\n'),

    # Aura, views and Ozone. Chromium's desktop UI is views drawn on Aura on
    # top of an Ozone platform; a desktop port that leaves these off has no
    # window system at all, and //chrome/test then references view targets
    # that were never added ("Label not in deps").
    ("build/config/ui.gni",
     "  use_aura = is_win || is_linux || is_chromeos || is_fuchsia\n",
     "  use_aura = is_win || is_linux || is_chromeos || is_fuchsia || is_haiku\n"),
    ("build/config/ui.gni",
     "  toolkit_views = is_mac || is_win || is_linux || is_chromeos || is_fuchsia\n",
     "  toolkit_views =\n"
     "      is_mac || is_win || is_linux || is_chromeos || is_fuchsia || is_haiku\n"),
    ("build/config/ozone.gni",
     "  use_ozone = is_chromeos || is_fuchsia || is_linux\n",
     "  use_ozone = is_chromeos || is_fuchsia || is_linux || is_haiku\n"),

    # grit keeps its own copy of the desktop-platform list and asserts it
    # agrees with toolkit_views.
    ("tools/grit/grit_args.gni",
     "assert(toolkit_views ==\n"
     "       (is_chromeos || is_fuchsia || is_linux || is_mac || is_win))\n",
     "assert(toolkit_views ==\n"
     "       (is_chromeos || is_fuchsia || is_linux || is_mac || is_win ||\n"
     "        is_haiku))\n"),

    # Component-updater OS name, used for the Widevine CDM directory layout.
    # Nothing ships a Haiku CDM, but the file is imported unconditionally by
    # //media, so the name has to exist.
    ("media/cdm/library_cdm/cdm_paths.gni",
     '} else if (is_fuchsia) {\n  component_os = "fuchsia"\n',
     '} else if (is_fuchsia) {\n  component_os = "fuchsia"\n'
     '} else if (is_haiku) {\n  component_os = "haiku"\n'),

    # content_unittests defines `data` only for the platforms it knows, then
    # appends to it unconditionally further down ("Undefined identifier").
    ("content/test/BUILD.gn",
     "  if (is_android || is_linux || is_chromeos || is_mac || is_win || is_fuchsia) {\n"
     "    data = [\n",
     "  if (is_android || is_linux || is_chromeos || is_mac || is_win ||\n"
     "      is_fuchsia || is_haiku) {\n"
     "    data = [\n"),

    # clang_rt: Chromium links the compiler-rt libraries that ship with its
    # bundled clang. There is no compiler-rt for Haiku, and none is wanted --
    # Haiku uses libgcc, and clang's own Haiku driver already passes -lgcc.
    # An empty config is the correct answer here, not a new directory name.
    ("build/config/clang/BUILD.gn",
     "template(\"clang_lib\") {\n"
     "  if (!defined(invoker.libname) || is_wasm) {\n",
     "template(\"clang_lib\") {\n"
     "  if (!defined(invoker.libname) || is_wasm || is_haiku) {\n"),

    # zlib's ARMv8 CRC32 path needs a way to ask the OS whether the CPU has
    # the crypto extensions, and cpu_features.c only knows getauxval, Fuchsia,
    # Windows and the Apple sysctls. Haiku has none of them. Turning the
    # optimisation off takes the CPU_NO_SIMD path, which is correct; claiming
    # ARMV8_OS_LINUX would compile and then call a getauxval that is not there.
    ("third_party/zlib/BUILD.gn",
     "use_arm_neon_optimizations =\n"
     "    (current_cpu == \"arm\" || current_cpu == \"arm64\") && !(is_win && !is_clang)\n",
     "use_arm_neon_optimizations =\n"
     "    (current_cpu == \"arm\" || current_cpu == \"arm64\") &&\n"
     "    !(is_win && !is_clang) && !is_haiku\n"),

    # Crash reporting. Crashpad has no Haiku port, so take the stub crash keys
    # the same way Fuchsia does until there is something to report to.
    ("components/crash/core/common/BUILD.gn",
     "  use_crash_key_stubs = is_fuchsia\n",
     "  use_crash_key_stubs = is_fuchsia || is_haiku\n"),

    # The WebUI New Tab Page. enable_session_service is `!is_android` and so
    # already true here, and //chrome/browser/ui pairs the two: the session
    # service block lists new_tab_page:impl in allow_circular_includes_from
    # while the dep itself is added only under enable_webui_ntp. With one on
    # and the other off, gn reports "Label not in deps".
    ("ui/webui/webui_features.gni",
     '        target_os == "win" || target_os == "mac" || target_os == "linux" ||\n'
     '        target_os == "chromeos" || is_desktop_android\n',
     '        target_os == "win" || target_os == "mac" || target_os == "linux" ||\n'
     '        target_os == "chromeos" || target_os == "haiku" ||\n'
     '        is_desktop_android\n'),

    # //chrome/browser/ui adds ui/lens:impl as a dep under
    # `!is_chromeos && !is_android` -- true for Haiku -- but lists it in
    # allow_circular_includes_from under a desktop list that omits Haiku.
    # The two have to agree or gn reports "Label not in deps".
    ("chrome/browser/ui/BUILD.gn",
     '  if (is_win || is_mac || is_linux || is_chromeos) {\n'
     '    sources += [\n'
     '      "views/profiles/incognito_menu_view.cc",\n',
     '  if (is_win || is_mac || is_linux || is_chromeos || is_haiku) {\n'
     '    sources += [\n'
     '      "views/profiles/incognito_menu_view.cc",\n'),

    # libxml ships pre-generated config headers per OS. Haiku is close enough
    # to the Linux set -- POSIX threads, POSIX I/O, no Windows or Apple
    # specifics -- that reusing it is right; anything genuinely wrong will
    # show up as a compile error rather than silently.
    ("third_party/libxml/BUILD.gn",
     'if (is_linux || is_chromeos || is_android || is_fuchsia) {\n'
     '  os_include = "linux"\n',
     'if (is_linux || is_chromeos || is_android || is_fuchsia || is_haiku) {\n'
     '  os_include = "linux"\n'),

    # content_shell asks for breakpad's symbol tools under is_posix, but
    # third_party/breakpad only defines them in its section headed
    # "Mac ---". Haiku is POSIX and reaches the consumer without the
    # definition, so exclude it here rather than build Mac symbol code.
    ("content/shell/BUILD.gn",
     '  if (is_posix) {\n'
     '    data_deps += [\n'
     '      "//third_party/breakpad:dump_syms",\n',
     '  if (is_posix && !is_haiku) {\n'
     '    data_deps += [\n'
     '      "//third_party/breakpad:dump_syms",\n'),

    # Dawn (WebGPU). Its common library is plain portable C++ -- the
    # backend-specific code lives elsewhere -- so it builds on Haiku, and
    # //third_party/dawn:proc_shared needs it whether or not any GPU backend
    # ends up working.
    ("third_party/dawn/src/dawn/common/BUILD.gn",
     'if (is_win || is_linux || is_chromeos || is_mac || is_fuchsia || is_android ||\n'
     '    is_ios || is_wasm) {\n',
     'if (is_win || is_linux || is_chromeos || is_mac || is_fuchsia || is_android ||\n'
     '    is_ios || is_wasm || is_haiku) {\n'),

    # SwiftShader's LLVM-backed Reactor, the software renderer Chromium falls
    # back to without a GPU. It bundles its own LLVM 10 and is portable C++;
    # the platform list is about which OSes SwiftShader has been built for,
    # not about anything Linux-specific in the code.
    ("third_party/swiftshader/src/Reactor/reactor.gni",
     "  supports_llvm = is_linux || is_chromeos || is_fuchsia || is_win || is_android\n",
     "  supports_llvm =\n"
     "      is_linux || is_chromeos || is_fuchsia || is_win || is_android ||\n"
     "      is_haiku\n"),

    # The telemetry build asks for breakpad's symbol tools the same way
    # content_shell did, in two places, and they are Mac-only for the same
    # reason.
    ("tools/perf/chrome_telemetry_build/BUILD.gn",
     '    data_deps += [ "//third_party/breakpad:dump_syms" ]\n',
     '    if (!is_haiku) {\n'
     '      data_deps += [ "//third_party/breakpad:dump_syms" ]\n'
     '    }\n'),
    ("tools/perf/chrome_telemetry_build/BUILD.gn",
     "  if (!is_win && !is_fuchsia) {\n    data_deps += [\n",
     "  if (!is_win && !is_fuchsia && !is_haiku) {\n    data_deps += [\n"),

    # SwiftShader's bundled LLVM 10 has a pre-generated config header per OS
    # (configs/linux, /darwin, /windows, ...). There is no Haiku one. The
    # Linux config is the closest fit -- ELF, pthreads, dlopen, no Apple or
    # Windows specifics -- and anything it gets wrong will show up as a
    # compile error rather than quietly.
    ("third_party/swiftshader/src/Reactor/BUILD.gn",
     '    if (is_linux || is_chromeos) {\n'
     '      include_dirs += [ "$llvm_dir/configs/linux/include/" ]\n',
     '    if (is_linux || is_chromeos || is_haiku) {\n'
     '      include_dirs += [ "$llvm_dir/configs/linux/include/" ]\n'),

    # The same choice again, in the bundled LLVM's own BUILD.gn.
    ("third_party/swiftshader/third_party/llvm-10.0/BUILD.gn",
     'if (is_linux || is_chromeos) {\n'
     '  llvm_include_dirs += [ "configs/linux/include/" ]\n',
     'if (is_linux || is_chromeos || is_haiku) {\n'
     '  llvm_include_dirs += [ "configs/linux/include/" ]\n'),

    # The clang target triple. Chromium hardcodes aarch64-linux-gnu for arm64
    # on anything that is not Android, Fuchsia or a ChromeOS device, so a
    # Haiku build compiles against clang's Linux assumptions: libc++ then
    # cannot resolve memcpy from Haiku's <string.h> and every translation
    # unit fails with "reference to unresolved using declaration".
    ("build/config/compiler_cpu_abi.gn",
     '  } else if (current_cpu == "arm64") {\n'
     '    if (is_clang && !is_android && !is_fuchsia && !is_chromeos_device) {\n'
     '      cpu_abi_cflags += [ "--target=aarch64-linux-gnu" ]\n'
     '      cpu_abi_ldflags += [ "--target=aarch64-linux-gnu" ]\n'
     '    }\n',
     '  } else if (current_cpu == "arm64") {\n'
     '    if (is_haiku) {\n'
     '      cpu_abi_cflags += [ "--target=aarch64-unknown-haiku" ]\n'
     '      cpu_abi_ldflags += [ "--target=aarch64-unknown-haiku" ]\n'
     '    } else if (is_clang && !is_android && !is_fuchsia &&\n'
     '               !is_chromeos_device) {\n'
     '      cpu_abi_cflags += [ "--target=aarch64-linux-gnu" ]\n'
     '      cpu_abi_ldflags += [ "--target=aarch64-linux-gnu" ]\n'
     '    }\n'),

    # perfetto keeps its own OS detection, independent of build_config.h, and
    # stops at #error for anything it does not recognise. Haiku is POSIX --
    # pthreads, clock_gettime, unix sockets -- so every flag is 0 and the
    # generic POSIX paths apply, the same shape FreeBSD uses just above.
    ("third_party/perfetto/include/perfetto/base/build_config.h",
     '#elif defined(__FreeBSD__)\n'
     '#define PERFETTO_BUILDFLAG_DEFINE_PERFETTO_OS_ANDROID() 0\n',
     '#elif defined(__HAIKU__)\n'
     '#define PERFETTO_BUILDFLAG_DEFINE_PERFETTO_OS_ANDROID() 0\n'
     '#define PERFETTO_BUILDFLAG_DEFINE_PERFETTO_OS_LINUX() 0\n'
     '#define PERFETTO_BUILDFLAG_DEFINE_PERFETTO_OS_LINUX_BUT_NOT_QNX() 0\n'
     '#define PERFETTO_BUILDFLAG_DEFINE_PERFETTO_OS_WIN() 0\n'
     '#define PERFETTO_BUILDFLAG_DEFINE_PERFETTO_OS_APPLE() 0\n'
     '#define PERFETTO_BUILDFLAG_DEFINE_PERFETTO_OS_MAC() 0\n'
     '#define PERFETTO_BUILDFLAG_DEFINE_PERFETTO_OS_IOS() 0\n'
     '#define PERFETTO_BUILDFLAG_DEFINE_PERFETTO_OS_WASM() 0\n'
     '#define PERFETTO_BUILDFLAG_DEFINE_PERFETTO_OS_FUCHSIA() 0\n'
     '#define PERFETTO_BUILDFLAG_DEFINE_PERFETTO_OS_NACL() 0\n'
     '#define PERFETTO_BUILDFLAG_DEFINE_PERFETTO_OS_QNX() 0\n'
     '#define PERFETTO_BUILDFLAG_DEFINE_PERFETTO_OS_APPLE_TVOS() 0\n'
     '#define PERFETTO_BUILDFLAG_DEFINE_PERFETTO_OS_FREEBSD() 0\n'
     '#elif defined(__FreeBSD__)\n'
     '#define PERFETTO_BUILDFLAG_DEFINE_PERFETTO_OS_ANDROID() 0\n'),

    # libc++'s ctype_base needs to know how the platform spells its character
    # classification table. Haiku's ctype.h is glibc-shaped -- the same
    # _ISspace/_ISprint/_IScntrl names, reached through __ctype_b_loc() -- so
    # it can share that branch outright. __regex_word there is 0x80, which is
    # one of the bits Haiku's enum leaves unused (it goes 0x0001, 0x0002,
    # 0x0004, 0x0008, then 0x0100 upwards), so the static_assert against
    # overlap still holds.
    #
    # This one belongs upstream in llvm's libc++ rather than in Chromium's
    # copy of it.
    ("third_party/libc++/src/include/__locale",
     "#  elif defined(__GLIBC__)\n"
     "  typedef unsigned short mask;\n",
     "#  elif defined(__GLIBC__) || defined(__HAIKU__)\n"
     "  typedef unsigned short mask;\n"),

    # __regex_word: the big-endian test reads `BYTE_ORDER == BIG_ENDIAN`, and
    # neither macro is defined here because <endian.h> has not been included.
    # The preprocessor treats both as 0, `0 == 0` is true, and the branch
    # calls _ISbit(), which is glibc-only. Requiring the macros to be defined
    # before comparing them fixes it for any libc that does not provide them,
    # not just Haiku.
    ("third_party/libc++/src/include/__locale",
     "#    if defined(__mips__) || (BYTE_ORDER == BIG_ENDIAN)\n",
     "#    if defined(__mips__) ||                                             \\\n"
     "        (defined(BYTE_ORDER) && defined(BIG_ENDIAN) && BYTE_ORDER == BIG_ENDIAN)\n"),

    # Haiku's <ctype.h> defines tolower, toupper, isalpha and the rest as
    # function-like macros with no __cplusplus guard, so they swallow the
    # member functions libc++ declares -- "expected member name or ';' after
    # declaration specifiers" at ctype::toupper. libstdc++ undefines them in
    # its own <cctype> for exactly this reason; do the same.
    ("third_party/libc++/src/include/cctype",
     "#  if !defined(_LIBCPP_HAS_NO_PRAGMA_SYSTEM_HEADER)\n"
     "#    pragma GCC system_header\n"
     "#  endif\n",
     "#  if defined(__HAIKU__)\n"
     "// Haiku's <ctype.h> defines these as function-like macros even in C++,\n"
     "// where they must be functions. libstdc++ undefines them here too.\n"
     "#    undef isalnum\n"
     "#    undef isalpha\n"
     "#    undef isblank\n"
     "#    undef iscntrl\n"
     "#    undef isdigit\n"
     "#    undef isgraph\n"
     "#    undef islower\n"
     "#    undef isprint\n"
     "#    undef ispunct\n"
     "#    undef isspace\n"
     "#    undef isupper\n"
     "#    undef isxdigit\n"
     "#    undef tolower\n"
     "#    undef toupper\n"
     "#  endif\n"
     "\n"
     "#  if !defined(_LIBCPP_HAS_NO_PRAGMA_SYSTEM_HEADER)\n"
     "#    pragma GCC system_header\n"
     "#  endif\n"),

    # CLOCK_BOOTTIME is a Linux clock that keeps counting across suspend.
    # Haiku has no equivalent, so fall back to the wall clock -- which is
    # exactly what this code already does when the runtime probe fails; it
    # just assumed the constant would always exist to probe with.
    ("third_party/perfetto/include/perfetto/base/time.h",
     "  static const clockid_t kBootTimeClockSource = [] {\n"
     "    struct timespec ts = {};\n"
     "    int res = clock_gettime(CLOCK_BOOTTIME, &ts);\n"
     "    return res == 0 ? CLOCK_BOOTTIME : kWallTimeClockSource;\n"
     "  }();\n",
     "  static const clockid_t kBootTimeClockSource = [] {\n"
     "#if defined(CLOCK_BOOTTIME)\n"
     "    struct timespec ts = {};\n"
     "    int res = clock_gettime(CLOCK_BOOTTIME, &ts);\n"
     "    return res == 0 ? CLOCK_BOOTTIME : kWallTimeClockSource;\n"
     "#else\n"
     "    // No boot-time clock on this platform; the wall clock is the\n"
     "    // fallback this function already used when the probe failed.\n"
     "    return kWallTimeClockSource;\n"
     "#endif\n"
     "  }();\n"),

    # CLOCK_MONOTONIC_RAW is a Linux extension. perfetto already falls back to
    # CLOCK_MONOTONIC for FreeBSD; test for the constant instead of naming
    # platforms, which covers Haiku and anything else that lacks it.
    ("third_party/perfetto/include/perfetto/base/time.h",
     "#if (PERFETTO_BUILDFLAG(PERFETTO_OS_FREEBSD))\n"
     "  // Note: CLOCK_MONOTONIC_RAW is a Linux extension.\n",
     "#if (PERFETTO_BUILDFLAG(PERFETTO_OS_FREEBSD)) || !defined(CLOCK_MONOTONIC_RAW)\n"
     "  // Note: CLOCK_MONOTONIC_RAW is a Linux extension.\n"),

    # timegm. Haiku has it in libroot and declares it in <bsd/time.h>, which
    # perfetto does not include; <time.h> alone does not bring it in.
    ("third_party/perfetto/include/perfetto/base/time.h",
     "#include <time.h>\n",
     "#include <time.h>\n"
     "\n"
     "#if defined(__HAIKU__)\n"
     "// timegm lives in libroot but is declared in <bsd/time.h>, which is not\n"
     "// on the include path here; <time.h> alone does not bring it in.\n"
     "#include <bsd/time.h>\n"
     "#endif\n"),

    # Thread ids. The generic fallback casts pthread_self() to an integer, and
    # on Haiku pthread_t is a pointer to a struct, so the cast is ill-formed.
    # Haiku's own thread_id is a small integer from find_thread(NULL), which
    # is what its debugger and tools display -- the right value to report.
    ("third_party/perfetto/include/perfetto/base/thread_utils.h",
     "#elif PERFETTO_BUILDFLAG(PERFETTO_OS_FUCHSIA)\n"
     "using PlatformThreadId = zx_koid_t;\n",
     "#elif defined(__HAIKU__)\n"
     "using PlatformThreadId = int32_t;\n"
     "inline PlatformThreadId GetThreadId() {\n"
     "  return static_cast<int32_t>(find_thread(nullptr));\n"
     "}\n"
     "#elif PERFETTO_BUILDFLAG(PERFETTO_OS_FUCHSIA)\n"
     "using PlatformThreadId = zx_koid_t;\n"),

    ("third_party/perfetto/include/perfetto/base/thread_utils.h",
     "#if PERFETTO_BUILDFLAG(PERFETTO_OS_FREEBSD)\n"
     "#include <pthread_np.h>\n"
     "#endif\n",
     "#if PERFETTO_BUILDFLAG(PERFETTO_OS_FREEBSD)\n"
     "#include <pthread_np.h>\n"
     "#endif\n"
     "#if defined(__HAIKU__)\n"
     "#include <OS.h>  // find_thread\n"
     "#endif\n"),

    # PartitionAlloc keeps its own copy of the platform detection, separate
    # from //build/build_config.h. Without Haiku there, PA_BUILDFLAG(IS_POSIX)
    # is 0 and ScopedClearLastError is never aliased, so PartitionAlloc's own
    # logging fails to compile.
    ("base/allocator/partition_allocator/src/partition_alloc/build_config.h",
     "#elif defined(__asmjs__) || defined(__wasm__)\n"
     "#define PA_IS_ASMJS\n"
     "#endif\n",
     "#elif defined(__asmjs__) || defined(__wasm__)\n"
     "#define PA_IS_ASMJS\n"
     "#elif defined(__HAIKU__)\n"
     "#define PA_IS_HAIKU\n"
     "#endif\n"),

    ("base/allocator/partition_allocator/src/partition_alloc/build_config.h",
     "    defined(PA_IS_QNX) || defined(PA_IS_SOLARIS) ||                          \\\n"
     "    PA_BUILDFLAG(IS_ANDROID) || PA_BUILDFLAG(IS_CHROMEOS)\n"
     "#define PA_IS_POSIX\n",
     "    defined(PA_IS_QNX) || defined(PA_IS_SOLARIS) ||                          \\\n"
     "    defined(PA_IS_HAIKU) ||                                                  \\\n"
     "    PA_BUILDFLAG(IS_ANDROID) || PA_BUILDFLAG(IS_CHROMEOS)\n"
     "#define PA_IS_POSIX\n"),

    # 234 of the 259 errors in //base come from one abseil header, and all of
    # them are the same thing: cctz declares its civil-time fields as
    # int_least8_t and its arguments as int_fast8_t. glibc makes both
    # `signed char`, so nothing narrows. Haiku makes int_fast8_t `int` --
    # which the standard allows, the "fast" types being implementation's
    # choice -- so every field initialiser narrows and
    # -Wimplicit-int-conversion, which abseil opts into via
    # prevent_unsafe_narrowing, turns each into an error.
    #
    # The values are months, days, hours, minutes and seconds; cctz documents
    # the ranges in the type aliases themselves ([1:12], [1:31], [0:59]). The
    # narrowing is safe, so drop the opt-in warning on Haiku rather than
    # rewrite upstream's header or disable it tree-wide.
    ("third_party/abseil-cpp/absl.gni",
     '        "//build/config/compiler:no_chromium_code",\n'
     '        "//build/config/compiler:prevent_unsafe_narrowing",\n',
     '        "//build/config/compiler:no_chromium_code",\n'
     '      ]\n'
     '      if (!is_haiku) {\n'
     '        configs += [ "//build/config/compiler:prevent_unsafe_narrowing" ]\n'
     '      }\n'
     '      configs += [\n'),

    # The Linux-only clock ids again, this time in the snapshot list. The
    # guard already excludes the platforms that lack them; Haiku joins it.
    ("third_party/perfetto/src/base/clock_snapshots.cc",
     "#if !PERFETTO_BUILDFLAG(PERFETTO_OS_APPLE) &&   \\\n",
     "#if !defined(__HAIKU__) &&                      \\\n"
     "    !PERFETTO_BUILDFLAG(PERFETTO_OS_APPLE) &&   \\\n"),

    # sys/syscall.h. PartitionAlloc includes it unconditionally but only uses
    # syscall() under IS_LINUX/IS_CHROMEOS guards, so the include can carry
    # the same condition. Haiku has no Linux syscall interface at all.
    ("base/allocator/partition_allocator/src/partition_alloc/page_allocator_internals_posix.h",
     "#include <sys/mman.h>\n"
     "#include <sys/syscall.h>\n",
     "#include <sys/mman.h>\n"
     "#if !defined(__HAIKU__)\n"
     "#include <sys/syscall.h>\n"
     "#endif\n"),

    ("base/allocator/partition_allocator/src/partition_alloc/partition_alloc_base/rand_util_posix.cc",
     "#include <fcntl.h>\n"
     "#include <sys/syscall.h>\n",
     "#include <fcntl.h>\n"
     "#if !defined(__HAIKU__)\n"
     "#include <sys/syscall.h>\n"
     "#endif\n"),

    # __THROW. The allocator shim uses it to give operator new/delete the
    # noexcept the standard requires. glibc defines it as `noexcept` in C++;
    # Haiku's <sys/cdefs.h> defines it empty, so the replacements come out
    # without the specification and clang rejects them against libc++'s
    # declarations. Define it properly for this header rather than dropping
    # the specification.
    ("base/allocator/partition_allocator/src/partition_alloc/shim/allocator_shim_override_cpp_symbols.h",
     "#define SHIM_CPP_SYMBOLS_EXPORT PA_NOINLINE\n"
     "#endif\n",
     "#define SHIM_CPP_SYMBOLS_EXPORT PA_NOINLINE\n"
     "#endif\n"
     "\n"
     "#if defined(__HAIKU__)\n"
     "// Haiku's <sys/cdefs.h> defines __THROW empty; in C++ operator new and\n"
     "// delete must be noexcept, which is what glibc's __THROW expands to.\n"
     "// Scoped to this header on purpose: the C shims in\n"
     "// allocator_shim_override_libc_symbols.h also use __THROW, and there it\n"
     "// has to stay empty to match Haiku's own malloc declarations.\n"
     "#undef __THROW\n"
     "#define __THROW noexcept\n"
     "#endif\n"),

    # ... and put it back at the end of the header, so nothing that includes
    # this one afterwards sees the redefinition.
    ("base/allocator/partition_allocator/src/partition_alloc/shim/allocator_shim_override_cpp_symbols.h",
     "#endif  // PARTITION_ALLOC_SHIM_ALLOCATOR_SHIM_OVERRIDE_CPP_SYMBOLS_H_\n",
     "#if defined(__HAIKU__)\n"
     "#undef __THROW\n"
     "#define __THROW\n"
     "#endif\n"
     "\n"
     "#endif  // PARTITION_ALLOC_SHIM_ALLOCATOR_SHIM_OVERRIDE_CPP_SYMBOLS_H_\n"),

    # abseil's GetTID, same shape as perfetto's: the generic fallback casts
    # pthread_self() to an integer and Haiku's pthread_t is a pointer.
    # find_thread(nullptr) returns Haiku's own thread_id, a small int, which
    # is what its tools display.
    ("third_party/abseil-cpp/absl/base/internal/sysinfo.cc",
     "#elif defined(__akaros__)\n",
     "#elif defined(__HAIKU__)\n"
     "\n"
     "pid_t GetTID() { return static_cast<pid_t>(find_thread(nullptr)); }\n"
     "\n"
     "#elif defined(__akaros__)\n"),

    ("third_party/abseil-cpp/absl/base/internal/sysinfo.cc",
     "#include \"absl/base/internal/sysinfo.h\"\n",
     "#include \"absl/base/internal/sysinfo.h\"\n"
     "\n"
     "#if defined(__HAIKU__)\n"
     "#include <OS.h>  // find_thread\n"
     "#endif\n"),

    # Haiku's own //base sources. Only one so far: system memory comes from
    # get_system_info() rather than /proc/meminfo, so process_metrics_linux.cc
    # does not apply and Chromium is otherwise left without
    # GetSystemMemoryInfo at all.
    ("base/BUILD.gn",
     '  if ((is_posix && !is_ios) || is_fuchsia) {\n'
     '    sources += [\n'
     '      "process/process_metrics_posix.cc",\n'
     '      "sync_socket_posix.cc",\n'
     '    ]\n'
     '  }\n',
     '  if ((is_posix && !is_ios) || is_fuchsia) {\n'
     '    sources += [\n'
     '      "process/process_metrics_posix.cc",\n'
     '      "sync_socket_posix.cc",\n'
     '    ]\n'
     '  }\n'
     '\n'
     '  if (is_haiku) {\n'
     '    sources += [ "process/process_metrics_haiku.cc" ]\n'
     '  }\n'),

    # setproctitle. Haiku has no equivalent and no writable argv area to
    # overwrite, so the process title cannot be changed after exec. The
    # function stays, doing nothing, the way Solaris and Fuchsia are already
    # excluded here.
    ("base/process/set_process_title.cc",
     "#if BUILDFLAG(IS_POSIX) && !BUILDFLAG(IS_APPLE) && !BUILDFLAG(IS_SOLARIS) && \\\n"
     "    !BUILDFLAG(IS_ANDROID) && !BUILDFLAG(IS_FUCHSIA)\n",
     "#if BUILDFLAG(IS_POSIX) && !BUILDFLAG(IS_APPLE) && !BUILDFLAG(IS_SOLARIS) && \\\n"
     "    !BUILDFLAG(IS_ANDROID) && !BUILDFLAG(IS_FUCHSIA) && !BUILDFLAG(IS_HAIKU)\n"),

    # SystemMemoryInfo and GetSystemMemoryInfo are declared only for the
    # platforms that implement them. process_metrics_haiku.cc implements them
    # for Haiku, so the declaration has to be visible here too.
    ("base/process/process_metrics.h",
     "#if BUILDFLAG(IS_WIN) || BUILDFLAG(IS_APPLE) || BUILDFLAG(IS_LINUX) ||      \\\n"
     "    BUILDFLAG(IS_CHROMEOS) || BUILDFLAG(IS_ANDROID) || BUILDFLAG(IS_AIX) || \\\n"
     "    BUILDFLAG(IS_FUCHSIA)\n",
     "#if BUILDFLAG(IS_WIN) || BUILDFLAG(IS_APPLE) || BUILDFLAG(IS_LINUX) ||      \\\n"
     "    BUILDFLAG(IS_CHROMEOS) || BUILDFLAG(IS_ANDROID) || BUILDFLAG(IS_AIX) || \\\n"
     "    BUILDFLAG(IS_FUCHSIA) || BUILDFLAG(IS_HAIKU)\n"),

    # The UI pump. Chromium runs its UI loop on the same epoll pump as I/O on
    # Linux and the BSDs; with the poll path in place that works on Haiku too.
    # A BWindow-driven pump belongs here eventually, alongside the Ozone
    # backend, but the port does not need one to start.
    ("base/message_loop/message_pump_for_ui.h",
     "#elif BUILDFLAG(IS_LINUX) || BUILDFLAG(IS_CHROMEOS) || BUILDFLAG(IS_BSD)\n"
     "#include \"base/message_loop/message_pump_epoll.h\"\n",
     "#elif BUILDFLAG(IS_LINUX) || BUILDFLAG(IS_CHROMEOS) || BUILDFLAG(IS_BSD) || \\\n"
     "    BUILDFLAG(IS_HAIKU)\n"
     "#include \"base/message_loop/message_pump_epoll.h\"\n"),

    ("base/message_loop/message_pump_for_ui.h",
     "#elif BUILDFLAG(IS_LINUX) || BUILDFLAG(IS_CHROMEOS) || BUILDFLAG(IS_BSD)\n"
     "using MessagePumpForUI = MessagePumpEpoll;\n",
     "#elif BUILDFLAG(IS_LINUX) || BUILDFLAG(IS_CHROMEOS) || BUILDFLAG(IS_BSD) || \\\n"
     "    BUILDFLAG(IS_HAIKU)\n"
     "using MessagePumpForUI = MessagePumpEpoll;\n"),

    # The sampling profiler's POSIX backend. stack_copier_signal wants
    # linux/futex.h and thread_delegate_posix reads architecture-specific
    # register context out of a Linux mcontext_t; Haiku has neither. Leaving
    # them out costs the sampling profiler, not the browser.
    ("base/BUILD.gn",
     '      "profiler/stack_copier_signal.cc",\n'
     '      "profiler/stack_copier_signal.h",\n'
     '      "profiler/thread_delegate_posix.cc",\n'
     '      "profiler/thread_delegate_posix.h",\n'
     '    ]\n',
     '    ]\n'
     '    if (!is_haiku) {\n'
     '      sources += [\n'
     '        "profiler/stack_copier_signal.cc",\n'
     '        "profiler/stack_copier_signal.h",\n'
     '        "profiler/thread_delegate_posix.cc",\n'
     '        "profiler/thread_delegate_posix.h",\n'
     '      ]\n'
     '    }\n'),

    # The abseil narrowing warnings again, this time raised by //base itself:
    # base enables prevent_unsafe_narrowing and includes cctz's headers, so
    # the absl.gni change does not reach them.
    #
    # cctz declares its civil-time fields as int_least8_t and its arguments as
    # int_fast8_t. glibc makes both `signed char`, so nothing narrows; Haiku
    # makes int_fast8_t `int`, which the standard allows, so every field
    # initialiser does. The values are months, days, hours, minutes and
    # seconds, with the ranges documented in the type aliases -- the narrowing
    # is safe.
    #
    # Chromium has a mechanism for exactly this: suppress by originating file
    # rather than by -Wno on the whole compilation. Scoped to cctz alone.
    ("build/config/warning_suppression.txt",
     "[unique-object-duplication]\n",
     "# cctz's civil-time fields narrow on any platform where int_fast8_t is\n"
     "# wider than int_least8_t, which includes Haiku. The ranges involved\n"
     "# ([1:12], [1:31], [0:59]) make the narrowing safe.\n"
     "[implicit-int-conversion]\n"
     "src:*{/,\\\\}third_party{/,\\\\}abseil-cpp{/,\\\\}absl{/,\\\\}time{/,\\\\}internal{/,\\\\}cctz{/,\\\\}*\n"
     "\n"
     "[unique-object-duplication]\n"),

    # Certificate verification. CertVerifyProc::CreateSystemVerifyProc has a
    # backend for each OS whose certificate store it knows, and #errors on the
    # rest. Haiku has no system certificate store to read, so the right answer
    # is chrome_root_store_only -- Chromium's own bundled roots, which is what
    # every desktop platform now uses anyway.
    ("net/features.gni",
     "  chrome_root_store_only = is_win || is_mac || is_linux || is_chromeos\n",
     "  chrome_root_store_only =\n"
     "      is_win || is_mac || is_linux || is_chromeos || is_haiku\n"),

    # Kerberos/GSSAPI. Haiku ships no gssapi.h and no MIT or Heimdal
    # implementation, so HTTP Negotiate authentication is unavailable. The
    # flag already excludes the platforms without one.
    ("net/features.gni",
     "  use_kerberos = !is_ios && !is_fuchsia && !is_castos && !is_cast_android\n",
     "  use_kerberos =\n"
     "      !is_ios && !is_fuchsia && !is_castos && !is_cast_android && !is_haiku\n"),
]


def main(src):
    import os
    applied = skipped = 0
    for rel, old, new in EDITS:
        p = os.path.join(src, rel)
        if not os.path.exists(p):
            print("  MISSING %s" % rel)
            continue
        s = open(p).read()
        if new.strip() in s or (old not in s and "is_haiku" in s):
            skipped += 1
            continue
        n = s.count(old)
        if n != 1:
            print("  DRIFTED %s (anchor found %d times)" % (rel, n))
            continue
        open(p, "w").write(s.replace(old, new))
        print("  %s" % rel)
        applied += 1
    print("  (%d applied, %d already done)" % (applied, skipped))


if __name__ == "__main__":
    main(sys.argv[1])
