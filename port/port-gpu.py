#!/usr/bin/env python3
"""Tell //gpu's control list which OS this is.

`GpuControlList::GetOsType()` has a branch per platform and `kOsAny` as the
fallback, and Haiku fell into the fallback. In a release build that is merely
wrong -- every entry in the software-rendering and driver-bug lists is then
compared against an OS that matches nothing, so the lists are silently inert.
With DCHECKs on it is fatal on the first GPU-info lookup:

    FATAL:gpu/config/gpu_control_list.cc:448] DCHECK failed:
    target_os_type != kOsAny

which is where the 2026-09-20 dcheck_always_on build stopped, before it had a
chance to say anything about V8.

Haiku belongs with Linux here. The lists are keyed on driver and vendor
behaviour, and this port's GL story is the Linux one.
"""
import os
import sys

EDITS = [
    ("gpu/config/gpu_control_list.cc",
     "#elif BUILDFLAG(IS_LINUX) || BUILDFLAG(IS_OPENBSD)\n"
     "  return kOsLinux;\n",
     "#elif BUILDFLAG(IS_LINUX) || BUILDFLAG(IS_OPENBSD) || BUILDFLAG(IS_HAIKU)\n"
     "  return kOsLinux;\n"),
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
    print("  gpu: %d applied, %d already done, %d drifted"
          % (applied, skipped, drifted))


if __name__ == "__main__":
    main(sys.argv[1])
