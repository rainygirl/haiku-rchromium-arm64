#!/usr/bin/env python3
"""A profile that survives a restart.

content_shell keeps its network context entirely in memory:
`ConfigureNetworkContextParamsForShell()` sets neither `file_paths` nor
`http_cache_directory`, so there is no cookie file and no disk cache. That is
right for a test binary and wrong for a browser somebody uses -- a sign-in
lasts exactly as long as the process, and every launch refetches everything.

Web storage does land on disk (this port does not force an off-the-record
context), which is why a page can sometimes look signed in after a restart
even with the cookie jar gone. It is not something to rely on.

`--user-data-dir` already says where the profile lives; this only puts the
network service's own files in it. In 154 the file names live in a
`NetworkContextFilePaths` struct that has to be created before it can be
filled, and `restore_old_session_cookies`/`persist_session_cookies` are still
required -- without them the cookie file exists and a session cookie, which is
what a login is until it is renewed, is still dropped on exit.

The same change was made on the x86 114 port; this is its arm64 twin.
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else "/work/chromium/src"
path = "%s/content/shell/browser/shell_content_browser_client.cc" % root
s = open(path).read()

if "context_params->file_paths->cookie_database_name" in s:
    print("  shell_content_browser_client.cc: already applied")
    raise SystemExit

old = ("  context_params->device_bound_sessions_enabled =\n"
       "      base::FeatureList::IsEnabled(net::features::kDeviceBoundSessions);\n"
       "}")
assert s.count(old) == 1, s.count(old)
new = ("  context_params->device_bound_sessions_enabled =\n"
       "      base::FeatureList::IsEnabled(net::features::kDeviceBoundSessions);\n"
       "\n"
       "  base::FilePath profile = context->GetPath();\n"
       "  if (!context->IsOffTheRecord() && !profile.empty()) {\n"
       "    context_params->file_paths =\n"
       "        network::mojom::NetworkContextFilePaths::New();\n"
       "    context_params->file_paths->data_directory =\n"
       "        profile.Append(FILE_PATH_LITERAL(\"Network\"));\n"
       "    context_params->file_paths->cookie_database_name =\n"
       "        base::FilePath(FILE_PATH_LITERAL(\"Cookies\"));\n"
       "    context_params->file_paths->http_server_properties_file_name =\n"
       "        base::FilePath(FILE_PATH_LITERAL(\"Network Persistent State\"));\n"
       "    context_params->restore_old_session_cookies = true;\n"
       "    context_params->persist_session_cookies = true;\n"
       # 114 had http_cache_directory on NetworkContextParams; 154 moved it
       # into NetworkContextFilePaths with the rest of the file names.
       "    context_params->file_paths->http_cache_directory =\n"
       "        profile.Append(FILE_PATH_LITERAL(\"Cache\"));\n"
       "  }\n"
       "}")
s = s.replace(old, new, 1)

if '#include "base/files/file_path.h"' not in s:
    anchor = '#include "content/shell/browser/shell_content_browser_client.h"'
    assert s.count(anchor) == 1, s.count(anchor)
    s = s.replace(anchor, anchor + '\n\n#include "base/files/file_path.h"', 1)

open(path, "w").write(s)
print("  shell_content_browser_client.cc: profile on disk")
