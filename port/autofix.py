#!/usr/bin/env python3
"""Add Haiku to whatever platform list gn just tripped over.

Two shapes cover nearly all of a new-OS port's gn work:

  1. `assert(is_win || is_mac || ...)` -- a file listing the platforms it
     supports. Haiku is a desktop system and belongs in the list.
  2. `assert(some_flag)` where some_flag is defined elsewhere as
     `is_linux || is_mac || is_win`. The same thing with one level of
     indirection.

Anything else is reported and left alone, so the unusual cases still get
looked at by hand.
"""
import os
import re
import subprocess
import sys

SRC = "/haiku-build/chromium/src"
PLATFORMS = r"\bis_(win|mac|linux|chromeos|android|fuchsia|ios)\b"


def read_block(path, line):
    """The statement starting at `line`, which may wrap over several lines."""
    lines = open(path).read().split("\n")
    start = line - 1
    depth = 0
    end = start
    for i in range(start, min(start + 12, len(lines))):
        depth += lines[i].count("(") - lines[i].count(")")
        end = i
        if depth <= 0:
            break
    return lines, start, end, "\n".join(lines[start:end + 1])


def add_haiku_to_expr(block):
    """Insert `|| is_haiku` before the closing paren, keeping any message."""
    idx = block.rfind(")")
    msg = re.search(r",\s*\"", block[:idx])
    at = msg.start() if msg else idx
    return block[:at] + " || is_haiku" + block[at:]


def patch_assert_list(path, line):
    lines, start, end, block = read_block(path, line)
    if "is_haiku" in block or not re.search(PLATFORMS, block):
        return None
    patched = add_haiku_to_expr(block)
    lines[start:end + 1] = patched.split("\n")
    open(path, "w").write("\n".join(lines))
    return patched


def patch_flag_definition(flag):
    """Find `flag = is_linux || ...` in a .gni and add Haiku to it."""
    pattern = r"^\s*" + re.escape(flag) + r" ="
    out = subprocess.run(
        ["grep", "-rn", "--include=*.gni", "--include=*.gn", "-E", pattern, "."],
        cwd=SRC, capture_output=True, text=True).stdout.strip()
    for entry in out.split("\n"):
        if not entry:
            continue
        parts = entry.split(":", 2)
        rel, lineno = parts[0], int(parts[1])
        path = os.path.join(SRC, rel.lstrip("./"))
        lines = open(path).read().split("\n")
        start = lineno - 1
        end = start
        # The definition may continue onto the following lines.
        while end + 1 < len(lines) and lines[end].rstrip().endswith(("||", "&&", "=")):
            end += 1
        block = "\n".join(lines[start:end + 1])
        if "is_haiku" in block or not re.search(PLATFORMS, block):
            continue
        lines[start:end + 1] = (block + " || is_haiku").split("\n")
        open(path, "w").write("\n".join(lines))
        return "%s:%d  %s" % (rel, lineno, (block + " || is_haiku").strip())
    return None


def patch_missing_target(label):
    """`//dir:name` names a target its own BUILD.gn only defines on some
    platforms. Add Haiku to the condition that guards it -- directly if the
    condition spells the platforms out, through the flag if it names one."""
    directory, _, name = label.partition(":")
    path = os.path.join(SRC, directory.lstrip("/"), "BUILD.gn")
    if not os.path.exists(path):
        return None
    lines = open(path).read().split("\n")
    define = re.compile(r'^\s*[a-z_]+\(\s*"' + re.escape(name) + r'"\s*\)')
    for i, line in enumerate(lines):
        if not define.match(line):
            continue
        # The guard is the nearest enclosing `if (...)` above the definition.
        for j in range(i - 1, max(i - 400, -1), -1):
            gm = re.match(r"^(\s*)if \((.*)\) \{\s*$", lines[j])
            if not gm:
                continue
            condition = gm.group(2)
            if "is_haiku" in condition:
                return None
            if re.search(PLATFORMS, condition):
                lines[j] = "%sif (%s || is_haiku) {" % (gm.group(1), condition)
                open(path, "w").write("\n".join(lines))
                return "%s:%d  if (%s || is_haiku)" % (path, j + 1, condition)
            fm = re.match(r"^([a-z_][a-z0-9_]*)$", condition.strip())
            if fm:
                return patch_flag_definition(fm.group(1))
            return None
    return None


def main():
    log = open("/tmp/gna.log").read()
    m = re.search(r"^ERROR at //([^:]+):(\d+):\d+: Assertion failed\.", log, re.M)
    if not m:
        um = re.search(r"^\s*needs (//[^ (]+)", log, re.M)
        if um:
            result = patch_missing_target(um.group(1))
            if result:
                print("PATCHED-GUARD %s" % um.group(1))
                print("  " + result)
                return 0
            print("GUARD-NOT-FOUND %s" % um.group(1))
            return 2
        print("NOT-AN-ASSERT")
        return 2
    rel, line = m.group(1), int(m.group(2))
    path = os.path.join(SRC, rel)

    result = patch_assert_list(path, line)
    if result:
        print("PATCHED %s:%d" % (rel, line))
        print(result)
        return 0

    _, _, _, block = read_block(path, line)
    fm = re.match(r"\s*assert\(\s*([a-z_][a-z0-9_]*)\s*[,)]", block)
    if fm:
        result = patch_flag_definition(fm.group(1))
        if result:
            print("PATCHED-FLAG %s" % fm.group(1))
            print("  " + result)
            return 0
        print("FLAG-NOT-FOUND %s" % fm.group(1))
        return 2

    print("NOT-A-PLATFORM-LIST")
    print(block)
    return 2


if __name__ == "__main__":
    sys.exit(main())
