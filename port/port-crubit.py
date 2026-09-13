#!/usr/bin/env python3
"""Switch crubit off for Haiku without touching every consumer.

crubit's cc_bindings_from_rs generates C++ bindings for Rust APIs. It links
the bundled rustc's internals, so it knows only the targets that rustc was
built with -- and this port replaces rustc with one that has a target the
bundle does not. A JSON target spec gets past "could not find specification"
and straight into "found crate `std` compiled by an incompatible version of
rustc": the tool is built against the bundled std. Rebuilding it is not
possible here either, since Chromium ships crubit as a prebuilt binary and
vendors no source.

`enable_cpp_api_from_rust` already exists to turn the bindings off, but
several consumers do not consult it -- //components/cbor guards on
`is_cronet_build`, //components/web_package and blink's platform on nothing --
so gn is left with unresolved dependencies. Patching each of them is possible
and was tried; it means editing dependency lists in four files whose shape
keeps changing, and it would have to be redone on every rebase.

target_os, not current_os: the host toolchain builds crubit's own support\ncrates too, and those are compiled with the replaced rustc whichever\ntoolchain asks for them. Keying on current_os leaves them enabled for the\nhost and they fail there instead.\n\nDoing it one level down is both smaller and steadier: `rust_target.gni`
already checks the flag, it just declines to declare the target at all. Have
it declare an empty group of the same name instead. Every consumer then keeps
its dependency, the dependency resolves, and it brings in nothing.
"""
import os
import sys

# port-rust-gni.py also edits build/config/rust.gni. Both are idempotent and
# touch different parts of it, but apply-haiku-port.sh runs that one first so
# the ordering is fixed rather than incidental.
EDITS = [
    ("build/config/rust.gni",
     "enable_cpp_api_from_rust = enable_rust && use_chromium_rust_toolchain &&\n"
     "                           !rust_prebuilt_stdlib && build_with_chromium\n",
     "enable_cpp_api_from_rust = enable_rust && use_chromium_rust_toolchain &&\n"
     "                           !rust_prebuilt_stdlib && build_with_chromium &&\n"
     '                           target_os != "haiku"\n'),

    ("build/rust/gni_impl/rust_target.gni",
     "    _cpp_api_from_rust_attributes = invoker.cpp_api_from_rust\n"
     "    if (!enable_cpp_api_from_rust) {\n"
     "      not_needed(_cpp_api_from_rust_attributes, \"*\")\n"
     "    } else {\n",
     "    _cpp_api_from_rust_attributes = invoker.cpp_api_from_rust\n"
     "    if (!enable_cpp_api_from_rust) {\n"
     "      not_needed(_cpp_api_from_rust_attributes, \"*\")\n"
     "\n"
     "      # Declare the target as an empty group rather than not at all.\n"
     "      # Consumers name these bindings unconditionally, so without\n"
     "      # something to resolve to gn stops with unresolved dependencies.\n"
     "      group(_cpp_api_from_rust_attributes.target_name) {\n"
     "        not_needed([ \"invoker\" ])\n"
     "      }\n"
     "    } else {\n"),

    # //components/cbor keeps a second switch of its own. USE_CBOR_RUST gates
    # the #include of the generated binding header and the code that calls
    # into it, but it is derived from is_cronet_build alone, so with crubit
    # off the header is gone while the include remains. The C++ CBOR parser
    # is still there and is what the flag falls back to.
    ("components/cbor/BUILD.gn",
     '  flags = [ "USE_CBOR_RUST=!$is_cronet_build" ]\n',
     '  flags = [ "USE_CBOR_RUST=!$is_cronet_build && $enable_cpp_api_from_rust" ]\n'),

    ("components/cbor/BUILD.gn",
     'import("//build/buildflag_header.gni")\n',
     'import("//build/buildflag_header.gni")\n'
     'import("//build/config/rust.gni")\n'),
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
    print("  crubit: %d applied, %d already done, %d drifted"
          % (applied, skipped, drifted))


if __name__ == "__main__":
    main(sys.argv[1])
