#!/usr/bin/env python3
"""Teach gn about a Haiku target.

Two changes: an is_haiku variable, and a default toolchain for
target_os == "haiku". is_posix is already `!is_win && !is_fuchsia`, so Haiku
becomes POSIX with no change at all, and is_linux stays false, which is what
we want -- Haiku is not Linux and should not take Linux paths.
"""
import sys

p = sys.argv[1]
s = open(p).read()

if 'target_os == "haiku"' in s:
    print("  BUILDCONFIG.gn: already patched")
    sys.exit(0)

# is_haiku. BUILDCONFIG.gn asks not to add is_* variables for "random
# lesser-used Unix systems", and for an upstream submission that is the right
# call -- current_os == "haiku" says the same thing. Out of tree it is not:
# dozens of .gni files enumerate desktop platforms as
# `is_linux || is_mac || is_win`, and every one of them needs Haiku added.
# One variable is far easier to keep correct across rebases than the same
# comparison spelled out in fifty places.
old_posix = """is_apple = is_ios || is_mac || is_watchos
is_posix = !is_win && !is_fuchsia"""
new_posix = """is_haiku = current_os == "haiku"

is_apple = is_ios || is_mac || is_watchos
is_posix = !is_win && !is_fuchsia"""
if "is_haiku = " not in s:
    assert s.count(old_posix) == 1, "is_posix block does not look as expected"
    s = s.replace(old_posix, new_posix)
    print("  BUILDCONFIG.gn: is_haiku")

# Attach the Haiku SDK config to every target. Without it -D_DEFAULT_SOURCE
# never reaches the compiler, and Haiku hides timegm, memrchr, strchrnul and
# the rest of its BSD/GNU extensions behind that macro.
old_cfg = """if (is_apple) {
  default_compiler_configs += [ "//build/config/compiler:enable_arc" ]
}"""
new_cfg = """if (is_apple) {
  default_compiler_configs += [ "//build/config/compiler:enable_arc" ]
}

if (is_haiku) {
  default_compiler_configs += [ "//build/config/haiku:sdk" ]
}"""
if "config/haiku:sdk" not in s:
    assert s.count(old_cfg) == 1, "default_compiler_configs does not look as expected"
    s = s.replace(old_cfg, new_cfg)
    print("  BUILDCONFIG.gn: haiku:sdk in default_compiler_configs")

old = '''} else if (target_os == "aix") {
  _default_toolchain = "//build/toolchain/aix:$target_cpu"'''
new = '''} else if (target_os == "haiku") {
  _default_toolchain = "//build/toolchain/haiku:clang_$target_cpu"
} else if (target_os == "aix") {
  _default_toolchain = "//build/toolchain/aix:$target_cpu"'''
assert s.count(old) == 1, "default toolchain chain does not look as expected"
s = s.replace(old, new)

# Cross-building from Linux needs a host toolchain as well; the Linux one is
# already correct for that, but the chain asserts on an unknown host_os only,
# so nothing more is needed there.
open(p, "w").write(s)
print("  BUILDCONFIG.gn: default toolchain for target_os=haiku")
