#!/usr/bin/env python3
"""Teach clang's Haiku driver the page size Haiku's loader expects from lld."""
import sys

p = sys.argv[1]
s = open(p).read()
old = '  CmdArgs.push_back("--eh-frame-hdr");'
new = '''  CmdArgs.push_back("--eh-frame-hdr");

  // Haiku's runtime_loader refuses an image whose PT_LOAD segments leave more
  // than MAX_PAGE_SIZE*2 of aggregate unused space between them:
  //
  //   // Check whether the segments have an unreasonable amount of unused
  //   // space inbetween.
  //   if (reservedSize > length + MAX_PAGE_SIZE * 2)
  //       return B_BAD_DATA;
  //          -- src/system/runtime_loader/images.cpp, map_image()
  //
  // lld defaults to a 64 KB max-page-size on AArch64 and gives read-only,
  // executable and writable data each their own segment, so even a
  // hello-world spans four segments over ~0x51000 while holding ~0x23000 of
  // content. It links, and then every run of it dies with
  //   runtime_loader: ...: Could not map image: Bad data
  // Haiku's page size is 4 KB; saying so packs the segments back inside what
  // the loader accepts. GNU ld is unaffected -- it already lays them out
  // this way, which is why -fuse-ld=bfd worked untouched.
  if (Triple.isAArch64()) {
    CmdArgs.push_back("-z");
    CmdArgs.push_back("max-page-size=4096");
  }'''

if "max-page-size" in s:
    print("  already patched")
    sys.exit(0)
assert s.count(old) == 1, "anchor not found once (%d)" % s.count(old)
open(p, "w").write(s.replace(old, new))
print("  Haiku.cpp patched")
