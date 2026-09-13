#!/usr/bin/env python3
"""Select R Chromium's Haiku ShellPlatformDelegate in content_shell.

content/shell/BUILD.gn compiles exactly one shell_platform_delegate_*.cc. On
Ozone with toolkit_views off it takes the aura one, which draws no chrome. For
Haiku we substitute shell_platform_delegate_haiku.cc (copied in by the generic
file step), which keeps aura content hosting and adds the native BeAPI toolbar.
Idempotent.
"""
import sys

def main(src):
    p = src + "/content/shell/BUILD.gn"
    s = open(p).read()
    if "shell_platform_delegate_haiku.cc" in s:
        print("  content_shell UI: already selected")
        return
    old = (
        '    } else {\n'
        '      sources += [\n'
        '        "browser/shell_platform_delegate_aura.cc",\n'
        '        "browser/shell_web_contents_view_delegate_aura.cc",\n'
        '      ]\n'
        '    }\n'
    )
    new = (
        '    } else if (is_haiku) {\n'
        '      sources += [\n'
        '        "browser/shell_platform_delegate_haiku.cc",\n'
        '        "browser/shell_web_contents_view_delegate_aura.cc",\n'
        '      ]\n'
        '    } else {\n'
        '      sources += [\n'
        '        "browser/shell_platform_delegate_aura.cc",\n'
        '        "browser/shell_web_contents_view_delegate_aura.cc",\n'
        '      ]\n'
        '    }\n'
    )
    n = s.count(old)
    if n != 1:
        print("  content_shell UI: DRIFTED (anchor found %d times)" % n)
        sys.exit(1)
    open(p, "w").write(s.replace(old, new, 1))
    print("  content_shell UI: haiku delegate selected")

if __name__ == "__main__":
    main(sys.argv[1])
