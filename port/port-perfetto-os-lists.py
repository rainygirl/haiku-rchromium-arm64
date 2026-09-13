#!/usr/bin/env python3
"""Add Haiku to perfetto's repeated "which POSIX systems" guards.

perfetto spells the same list out in a dozen files:

    #if PERFETTO_BUILDFLAG(PERFETTO_OS_LINUX) ||   \\
        PERFETTO_BUILDFLAG(PERFETTO_OS_ANDROID) || \\
        ... || PERFETTO_BUILDFLAG(PERFETTO_OS_FREEBSD) || ...

It gates the things a POSIX system can do -- shared memory over file
descriptors, unix sockets, mmap. Haiku does all of them, so it belongs in
every one of these lists. Editing them by hand invites missing one.
"""
import os
import re
import subprocess
import sys

src = sys.argv[1]
root = os.path.join(src, "third_party/perfetto")

# The FreeBSD term is the anchor: it is the last OS added to these lists and
# appears in all of them.
ANCHOR = "PERFETTO_BUILDFLAG(PERFETTO_OS_FREEBSD)"
NEW = "PERFETTO_BUILDFLAG(PERFETTO_OS_FREEBSD) || \\\n    defined(__HAIKU__)"

out = subprocess.run(["grep", "-rl", ANCHOR, "."], cwd=root,
                     capture_output=True, text=True).stdout.split()
patched = skipped = 0
for rel in out:
    p = os.path.join(root, rel)
    s = open(p).read()
    if "__HAIKU__" in s:
        skipped += 1
        continue
    # Only touch the multi-line guards, where FreeBSD is followed by " || \".
    n = s.count(ANCHOR + " || \\")
    if n == 0:
        skipped += 1
        continue
    s = s.replace(ANCHOR + " || \\", NEW.replace("\n", "\n") + " || \\", 1) \
        if False else s.replace(
            ANCHOR + " || \\",
            ANCHOR + " ||   \\\n    defined(__HAIKU__) || \\", 1)
    open(p, "w").write(s)
    print("  %s" % rel.lstrip("./"))
    patched += 1

print("  (%d patched, %d skipped)" % (patched, skipped))
