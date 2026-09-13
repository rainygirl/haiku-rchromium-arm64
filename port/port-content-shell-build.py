#!/usr/bin/env python3
"""Source fixes to build content_shell (not just //chrome) for Haiku.

content_shell pulls in test-support and shell code that //chrome does not, and
two spots assume POSIX-is-Linux. Idempotent; each is a no-op if already applied.
"""
import sys


def patch(path, old, new, label):
    s = open(path).read()
    if new in s:
        print("  %s: already applied" % label)
        return
    if old not in s:
        print("  %s: ANCHOR NOT FOUND" % label)
        sys.exit(1)
    open(path, "w").write(s.replace(old, new, 1))
    print("  %s: applied" % label)


def main(src):
    # 1. perfetto test util: Haiku has no mincore(); assume resident, like NaCL.
    patch(
        src + "/third_party/perfetto/src/base/test/vm_test_utils.cc",
        "#elif PERFETTO_BUILDFLAG(PERFETTO_OS_NACL)\n"
        "  // mincore isn't available on NaCL.\n"
        "  ignore_result(page_size);\n"
        "  return true;\n"
        "#else",
        "#elif PERFETTO_BUILDFLAG(PERFETTO_OS_NACL)\n"
        "  // mincore isn't available on NaCL.\n"
        "  ignore_result(page_size);\n"
        "  return true;\n"
        "#elif defined(__HAIKU__)\n"
        "  // Haiku has no mincore(); page residency is unmeasurable, so assume\n"
        "  // resident.\n"
        "  ignore_result(page_size);\n"
        "  return true;\n"
        "#else",
        "perfetto vm_test_utils mincore")

    # 2. content_shell user data dir for Haiku, so the trailing return is
    #    reachable (the #else returns false -> -Wunreachable-code-return).
    patch(
        src + "/content/shell/common/shell_paths.cc",
        "#elif BUILDFLAG(IS_FUCHSIA)\n"
        "  *result = base::FilePath(base::kPersistedDataDirectoryPath)\n"
        "                .Append(FILE_PATH_LITERAL(\"content_shell\"));\n"
        "#else\n"
        "  NOTIMPLEMENTED();\n"
        "  return false;\n"
        "#endif",
        "#elif BUILDFLAG(IS_FUCHSIA)\n"
        "  *result = base::FilePath(base::kPersistedDataDirectoryPath)\n"
        "                .Append(FILE_PATH_LITERAL(\"content_shell\"));\n"
        "#elif BUILDFLAG(IS_HAIKU)\n"
        "  CHECK(base::PathService::Get(base::DIR_HOME, result));\n"
        "  *result =\n"
        "      result->Append(\"config\").Append(\"settings\").Append(\"content_shell\");\n"
        "#else\n"
        "  NOTIMPLEMENTED();\n"
        "  return false;\n"
        "#endif",
        "content_shell shell_paths user data dir")


if __name__ == "__main__":
    main(sys.argv[1])
