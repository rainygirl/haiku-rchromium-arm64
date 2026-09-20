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

# crubit's cc_bindings_from_rs is not switched off here any more. It links
# rustc's internals, so it only understands metadata from the rustc that built
# it -- and Chromium's bundled binary is x86_64 besides, so on this host there
# was nothing to run. ../rust/build-crubit-arm64.sh builds it against the
# replaced rustc instead, which also teaches it aarch64-unknown-haiku. Turning
# it off cost two features that have no other implementation: blink's
# OpenType format checks (variable and colour fonts) and web_package's signed
# bundle verification, both of which name the generated headers
# unconditionally.

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
