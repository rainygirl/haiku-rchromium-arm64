#!/usr/bin/env python3
"""Select R Chromium's Haiku ShellPlatformDelegate in content_shell.

content/shell/BUILD.gn compiles exactly one shell_platform_delegate_*.cc, chosen
by shell_use_toolkit_views. On Haiku toolkit_views is forced true (the desktop-
platform assert in tools/grit/grit_args.gni lists is_haiku), so the views
delegate would be picked -- drawing an in-content Back/Forward/Reload toolbar on
top of R Chromium's own native BeAPI toolbar. So select the Haiku delegate
first, before the views branch, and take the aura content-view delegate with it.
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
        '    if (shell_use_toolkit_views) {\n'
        '      sources += [\n'
        '        "browser/shell_platform_delegate_views.cc",\n'
        '        "browser/shell_web_contents_view_delegate_views.cc",\n'
        '      ]\n'
        '      public_deps += [ "//ui/base/mojom:ui_base_types" ]\n'
        '      deps += [\n'
        '        "//ui/color:color_headers",\n'
        '        "//ui/resources",\n'
        '        "//ui/views:test_support",\n'
        '        "//ui/views/controls/webview",\n'
        '        "//ui/wm:test_support",\n'
        '      ]\n'
        '    } else {\n'
        '      sources += [\n'
        '        "browser/shell_platform_delegate_aura.cc",\n'
        '        "browser/shell_web_contents_view_delegate_aura.cc",\n'
        '      ]\n'
        '    }\n'
    )
    new = (
        '    if (is_haiku) {\n'
        '      # R Chromium draws its own native BeAPI toolbar in the ozone\n'
        '      # layer, so content_shell takes the aura content path and this\n'
        '      # Haiku delegate, never the in-content views toolbar -- even\n'
        '      # though toolkit_views is forced true for Haiku.\n'
        '      sources += [\n'
        '        "browser/shell_platform_delegate_haiku.cc",\n'
        '        "browser/shell_web_contents_view_delegate_aura.cc",\n'
        '      ]\n'
        '    } else if (shell_use_toolkit_views) {\n'
        '      sources += [\n'
        '        "browser/shell_platform_delegate_views.cc",\n'
        '        "browser/shell_web_contents_view_delegate_views.cc",\n'
        '      ]\n'
        '      public_deps += [ "//ui/base/mojom:ui_base_types" ]\n'
        '      deps += [\n'
        '        "//ui/color:color_headers",\n'
        '        "//ui/resources",\n'
        '        "//ui/views:test_support",\n'
        '        "//ui/views/controls/webview",\n'
        '        "//ui/wm:test_support",\n'
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
    print("  content_shell UI: haiku delegate selected (is_haiku first)")


if __name__ == "__main__":
    main(sys.argv[1])
