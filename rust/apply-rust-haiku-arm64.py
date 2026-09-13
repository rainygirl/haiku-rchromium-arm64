#!/usr/bin/env python3
"""Add aarch64-unknown-haiku to rustc.

Rust ships Haiku targets for i686 and x86_64 only. Chromium cannot be built
for Haiku arm64 without this one, because Chromium's Rust cannot be switched
off -- skia's bridge_rust_side is a hard dependency.

Two changes: the target spec itself, and its entry in the target list.
"""
import os
import shutil
import sys

src = sys.argv[1]
here = os.path.dirname(os.path.abspath(__file__))
spec_dir = os.path.join(src, "compiler/rustc_target/src/spec")

# 1. The spec.
dst = os.path.join(spec_dir, "targets/aarch64_unknown_haiku.rs")
shutil.copy(os.path.join(here, "aarch64_unknown_haiku.rs"), dst)
print("  added targets/aarch64_unknown_haiku.rs")

# 2. The registration, kept in the order the file already uses: the list is
#    sorted by architecture within each OS group, and aarch64 comes first.
p = os.path.join(spec_dir, "mod.rs")
s = open(p).read()
if '"aarch64-unknown-haiku"' in s:
    print("  mod.rs: already registered")
else:
    old = '    ("i686-unknown-haiku", i686_unknown_haiku),'
    new = ('    ("aarch64-unknown-haiku", aarch64_unknown_haiku),\n'
           '    ("i686-unknown-haiku", i686_unknown_haiku),')
    assert s.count(old) == 1, "target list does not look as expected"
    open(p, "w").write(s.replace(old, new))
    print("  mod.rs: registered aarch64-unknown-haiku")
