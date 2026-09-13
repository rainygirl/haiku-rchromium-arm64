#!/bin/sh
# Fix-and-repeat until gn gen succeeds or hits something the autofixer does
# not recognise.
cd /haiku-build/chromium
i=0
while [ $i -lt 200 ]; do
  i=$((i+1))
  if /haiku-build/chromium/port/iterate.sh > /tmp/it.log 2>&1; then
    echo "=== GN GEN SUCCEEDED after $((i-1)) fixes"; exit 0
  fi
  out=$(python3 /haiku-build/chromium/port/autofix.py 2>&1)
  case "$out" in
    PATCHED*) echo "$out" | head -1 ;;
    *) echo "=== stopped after $((i-1)) fixes"; head -6 /tmp/it.log; echo "$out" | head -3; exit 1 ;;
  esac
done
