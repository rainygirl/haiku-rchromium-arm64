#!/usr/bin/env python3
"""Give the Haiku target a Rust ABI triple.

Rust ships Haiku targets for i686 and x86_64 only; there is no
aarch64-unknown-haiku, which is why Chromium for Haiku arm64 cannot be built
until that target is added to rustc. chromium/rust/ does exactly that -- a target spec plus a
std built for it -- so all three triples are wired up here. A stock rustc
still only has the x86_64 and i686 ones.
"""
import sys, os

src = sys.argv[1]
p = os.path.join(src, "build/config/rust.gni")
s = open(p).read()

if 'unknown-haiku' in s:
    print("  rust.gni: already patched")
else:
    old = '''} else if (is_mac) {
  if (current_cpu == "arm64") {
    rust_abi_target = "aarch64-apple-darwin"'''
    new = '''} else if (current_os == "haiku") {
  if (current_cpu == "x64") {
    rust_abi_target = "x86_64-unknown-haiku"
  } else if (current_cpu == "x86") {
    rust_abi_target = "i686-unknown-haiku"
  } else if (current_cpu == "arm64") {
    # Not an upstream Rust target: added by chromium/rust/, which patches
    # rustc with a spec for it and builds a std. Use a rustc built that way,
    # or this fails at link time with "can't find crate for `std`".
    rust_abi_target = "aarch64-unknown-haiku"
  } else {
    assert(false, "no Rust Haiku target for $current_cpu")
  }
} else if (is_mac) {
  if (current_cpu == "arm64") {
    rust_abi_target = "aarch64-apple-darwin"'''
    assert s.count(old) == 1, "rust.gni does not look as expected"
    open(p, "w").write(s.replace(old, new))
    print("  rust.gni: Haiku ABI triples")

# crubit's cc_bindings_from_rs generates C++ bindings for Rust APIs. It links
# the bundled rustc's internals, so it only knows the targets that rustc was
# built with -- and this port replaces rustc with one that has a target the
# bundle does not. Rebuilding crubit against the replacement is possible in
# principle and a good deal of work; nothing reached so far needs the C++
# side of a Rust API, so it is off here instead.
s2 = open(os.path.join(src, "build/config/rust.gni")).read()
old_crubit = """enable_cpp_api_from_rust = enable_rust && use_chromium_rust_toolchain &&
                           !rust_prebuilt_stdlib && build_with_chromium"""
new_crubit = (
    "enable_cpp_api_from_rust = enable_rust && use_chromium_rust_toolchain &&\n"
    "                           !rust_prebuilt_stdlib && build_with_chromium &&\n"
    '                           current_os != "haiku"'
)
if "current_os != \"haiku\"" not in s2:
    assert s2.count(old_crubit) == 1, "crubit condition does not look as expected"
    open(os.path.join(src, "build/config/rust.gni"), "w").write(
        s2.replace(old_crubit, new_crubit))
    print("  rust.gni: crubit off for Haiku")

# Chromium checks the triple against a list of ones it knows.
t = os.path.join(src, "build/rust/known-target-triples.txt")
lines = open(t).read().splitlines()
added = [x for x in ("aarch64-unknown-haiku", "i686-unknown-haiku",
                    "x86_64-unknown-haiku") if x not in lines]
if added:
    lines = sorted(set(lines + added))
    open(t, "w").write("\n".join(lines) + "\n")
    print("  known-target-triples.txt: " + ", ".join(added))
else:
    print("  known-target-triples.txt: already patched")
