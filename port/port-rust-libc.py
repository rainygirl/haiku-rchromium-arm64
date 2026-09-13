#!/usr/bin/env python3
"""Teach the vendored libc crate about aarch64 Haiku.

third_party/rust/.../libc-v0_2 already carries src/unix/haiku, but only
x86_64.rs -- the aarch64 arm of the cfg_if is a commented-out TODO upstream.
Anything on the target side that reaches for mcontext_t or ucontext_t
therefore fails to resolve.

The struct is Haiku's own: signal.h does `typedef struct vregs mcontext_t`,
so unlike x86_64 there is no separate FPU-state type to mirror.
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

EDITS = [
    ("third_party/rust/chromium_crates_io/vendor/libc-v0_2/src/unix/haiku/mod.rs",
     "    } else if #[cfg(target_arch = \"aarch64\")] {\n"
     "        // TODO\n"
     "        // mod aarch64;\n"
     "        // pub use self::aarch64::*;\n"
     "    }\n",
     "    } else if #[cfg(target_arch = \"aarch64\")] {\n"
     "        mod aarch64;\n"
     "        pub use self::aarch64::*;\n"
     "    }\n"),
]

COPIES = [
    ("rust/aarch64.rs",
     "third_party/rust/chromium_crates_io/vendor/libc-v0_2/src/unix/haiku/aarch64.rs"),
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
        s_path = os.path.join(HERE, "files", rel_src)
        d_path = os.path.join(src, rel_dst)
        if not os.path.exists(s_path):
            print("  MISSING source %s" % rel_src)
            continue
        if not (os.path.exists(d_path)
                and open(d_path).read() == open(s_path).read()):
            shutil.copyfile(s_path, d_path)
            copied += 1

    print("  rust-libc: %d applied, %d already done, %d drifted, %d copied"
          % (applied, skipped, drifted, copied))


if __name__ == "__main__":
    main(sys.argv[1])
