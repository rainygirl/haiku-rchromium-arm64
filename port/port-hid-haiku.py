#!/usr/bin/env python3
"""A HidService for Haiku, because there being none is fatal.

`HidService::Create()` returns nullptr on a platform it does not know, and
`HidManagerImpl`'s constructor then does

	DCHECK(hid_service_);
	hid_service_observation_.Observe(hid_service_.get());

The DCHECK is compiled out of a release build. What is left is Observe() on a
null pointer: `HidService::AddObserver()` adds 0x40 to reach its
`observer_list_` member and the load faults there.

    Received signal 11 SEGV_MAPERR 0000000000000040
    device::DeviceService::BindHidManager
      -> device::HidManagerImpl::HidManagerImpl()
        -> device::HidService::AddObserver     (tail call, x0 = nullptr)
          -> base::ObserverList<>::AddObserver
               ldp x10, x8, [x0]               <- x0 = 0x40

x.com's sign-in page asks for the HID device list -- a passkey is a HID
device -- so entering a handle and pressing Continue killed R Twitter every
time. `navigator.hid.getDevices()` on its own does NOT reproduce it: with no
granted permissions it answers with an empty list without ever binding the
service.

Fuchsia is in the same position and answers it with a stub that finds nothing;
`files/services/device/hid/hid_service_haiku.{h,cc}` is that stub for Haiku.
This puts it in the build and in Create().
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else "/work/chromium/src"
done = 0

path = "%s/services/device/hid/hid_service.cc" % root
s = open(path).read()
if "HidServiceHaiku" in s:
    print("  hid_service.cc: already applied")
else:
    old = ("#elif BUILDFLAG(IS_ANDROID)\n"
           "  return std::make_unique<HidServiceAndroid>();\n"
           "#else\n"
           "  return nullptr;\n"
           "#endif")
    assert s.count(old) == 1, s.count(old)
    new = ("#elif BUILDFLAG(IS_ANDROID)\n"
           "  return std::make_unique<HidServiceAndroid>();\n"
           "#elif BUILDFLAG(IS_HAIKU)\n"
           "  return std::make_unique<HidServiceHaiku>();\n"
           "#else\n"
           "  return nullptr;\n"
           "#endif")
    s = s.replace(old, new, 1)
    anchor = '#include "services/device/hid/hid_service.h"'
    assert s.count(anchor) == 1, s.count(anchor)
    s = s.replace(anchor,
                  anchor + "\n\n#if BUILDFLAG(IS_HAIKU)\n"
                  '#include "services/device/hid/hid_service_haiku.h"\n'
                  "#endif", 1)
    open(path, "w").write(s)
    print("  hid_service.cc: Haiku arm added")
    done += 1

path = "%s/services/device/hid/BUILD.gn" % root
s = open(path).read()
if "hid_service_haiku" in s:
    print("  BUILD.gn: already applied")
else:
    old = ('  if (is_fuchsia) {\n'
           '    sources += [\n'
           '      "hid_service_fuchsia.cc",\n'
           '      "hid_service_fuchsia.h",\n'
           '    ]\n'
           '  }')
    assert s.count(old) == 1, s.count(old)
    new = old + ('\n\n  if (is_haiku) {\n'
                 '    sources += [\n'
                 '      "hid_service_haiku.cc",\n'
                 '      "hid_service_haiku.h",\n'
                 '    ]\n'
                 '  }')
    open(path, "w").write(s.replace(old, new, 1))
    print("  BUILD.gn: Haiku sources added")
    done += 1

print("hid haiku: %d" % done)
