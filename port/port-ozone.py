#!/usr/bin/env python3
"""Register the Haiku Ozone platform.

Chromium picks an Ozone platform at build time from gn flags, and generates
the constructor list from the platform names in ui/ozone/BUILD.gn. Adding a
platform therefore means three things: declaring the flag, turning it on for
Haiku, and naming the source_set that implements it.

Without this, target_os="haiku" falls through every branch in ozone.gni and
lands on the headless default -- which builds and runs, but never puts a
window on screen.
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

EDITS = [
    ("build/config/ozone.gni",
     "  # Compile the 'headless' platform.\n"
     "  ozone_platform_headless = false\n",
     "  # Compile the 'haiku' platform.\n"
     "  ozone_platform_haiku = false\n"
     "\n"
     "  # Compile the 'headless' platform.\n"
     "  ozone_platform_headless = false\n"),

    # Haiku gets its own platform rather than the headless default. headless
    # stays compiled in so --ozone-platform=headless still works, which is
    # what the tests and the screenshot path use.
    ("build/config/ozone.gni",
     "    } else if (is_fuchsia) {\n"
     "      ozone_platform = \"flatland\"\n"
     "      ozone_platform_flatland = true\n"
     "    }\n",
     "    } else if (is_fuchsia) {\n"
     "      ozone_platform = \"flatland\"\n"
     "      ozone_platform_flatland = true\n"
     "    } else if (is_haiku) {\n"
     "      ozone_platform = \"haiku\"\n"
     "      ozone_platform_haiku = true\n"
     "    }\n"),

    ("ui/ozone/BUILD.gn",
     "if (ozone_platform_headless) {\n"
     "  ozone_platforms += [ \"headless\" ]\n",
     "if (ozone_platform_haiku) {\n"
     "  ozone_platforms += [ \"haiku\" ]\n"
     "  ozone_platform_deps += [ \"platform/haiku\" ]\n"
     "}\n"
     "\n"
     "if (ozone_platform_headless) {\n"
     "  ozone_platforms += [ \"headless\" ]\n"),
]

# The whole platform directory, copied in rather than patched.
COPY_DIR = ("ozone/haiku", "ui/ozone/platform/haiku")


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
    src_dir = os.path.join(HERE, "files", COPY_DIR[0])
    dst_dir = os.path.join(src, COPY_DIR[1])
    if os.path.isdir(src_dir):
        os.makedirs(dst_dir, exist_ok=True)
        for name in sorted(os.listdir(src_dir)):
            s_path = os.path.join(src_dir, name)
            d_path = os.path.join(dst_dir, name)
            if not os.path.isfile(s_path):
                continue
            if os.path.exists(d_path) and open(d_path).read() == open(s_path).read():
                continue
            shutil.copyfile(s_path, d_path)
            copied += 1
    else:
        print("  MISSING source dir %s" % src_dir)

    print("  ozone: %d applied, %d already done, %d drifted, %d files copied"
          % (applied, skipped, drifted, copied))


if __name__ == "__main__":
    main(sys.argv[1])
