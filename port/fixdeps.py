#!/usr/bin/env python3
"""Add Haiku to the platform guards around targets gn could not resolve.

Once every BUILD.gn parses, what is left is targets that exist only for the
platforms their file already knew about. The consumer is reached on Haiku but
the definition is not, so gn reports "Unresolved dependencies".

For each missing target this finds the `if (...)` block enclosing its
definition and adds is_haiku to it. Guards that are not platform lists are
reported and left alone.
"""
import os
import re
import subprocess
import sys

SRC = "/haiku-build/chromium/src"
PLATFORMS = r"\bis_(win|mac|linux|chromeos|android|fuchsia|ios)\b"
DEFN = r"^\s*(source_set|static_library|component|group|test|executable|" \
       r"shared_library|jumbo_source_set|bundle_data|action)\(\"%s\"\)"


def enclosing_if(lines, defn_line):
    """The `if (` whose block contains defn_line, by brace depth."""
    depth = 0
    stack = []
    for i in range(defn_line):
        line = lines[i]
        m = re.match(r"\s*(\}\s*else\s*)?if \(", line)
        if m and line.rstrip().endswith("{"):
            stack.append((i, depth))
        elif m:
            # multi-line condition: find where it opens
            stack.append((i, depth))
        depth += line.count("{") - line.count("}")
        while stack and stack[-1][1] >= depth:
            stack.pop()
    return stack[-1][0] if stack else None


def patch(target):
    d, n = target.split(":")
    path = os.path.join(SRC, d.lstrip("/"), "BUILD.gn")
    if not os.path.exists(path):
        return "no BUILD.gn: %s" % target
    text = open(path).read()
    lines = text.split("\n")
    m = re.search(DEFN % re.escape(n), text, re.M)
    if not m:
        return "definition not found: %s" % target
    defn_line = text[:m.start()].count("\n")

    i = enclosing_if(lines, defn_line)
    if i is None:
        return "no enclosing if: %s" % target
    # The condition may wrap; take until the line that opens the block.
    end = i
    while end < len(lines) and not lines[end].rstrip().endswith("{"):
        end += 1
    cond = "\n".join(lines[i:end + 1])
    if "is_haiku" in cond:
        return "already: %s" % target
    if not re.search(PLATFORMS, cond):
        return "not a platform guard: %s -> %s" % (target, cond.strip())
    idx = cond.rfind(")")
    new = cond[:idx] + " || is_haiku" + cond[idx:]
    lines[i:end + 1] = new.split("\n")
    open(path, "w").write("\n".join(lines))
    return "PATCHED %s\n    %s" % (target, new.strip().replace("\n", " "))


def main():
    log = open("/tmp/gna.log").read()
    targets = sorted(set(re.findall(r"needs (//[^(]+)\(", log)))
    if not targets:
        print("no unresolved dependencies in the log")
        return 1
    for t in targets:
        print("  " + patch(t.strip()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
