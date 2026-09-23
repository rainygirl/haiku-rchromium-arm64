#!/bin/sh
# Run gn gen and print just the failing site, for the fix-and-repeat loop.
#
# target_sysroot: build/config/sysroot.gni leaves `sysroot` empty otherwise,
# and //build/modules then looks for the system headers at an absolute path.
cd /haiku-build/chromium/src
timeout 900 ./buildtools/linux64/gn gen out/haiku-arm64 --args="
  target_os=\"haiku\"
  target_cpu=\"arm64\"
  is_debug=false
  symbol_level=0
  target_sysroot=\"/root/pybuild/sysroot\"
  haiku_sysroot=\"/root/pybuild/sysroot\"
  use_partition_alloc_as_malloc=false
  enable_backup_ref_ptr_support=false
  use_allocator_shim=false
" > /tmp/gna.log 2>&1
rc=$?
if [ $rc -eq 0 ]; then echo "GN GEN SUCCEEDED"; exit 0; fi
grep -m1 -A5 "^ERROR" /tmp/gna.log
exit 1
