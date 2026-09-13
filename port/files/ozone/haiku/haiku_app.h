// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef UI_OZONE_PLATFORM_HAIKU_HAIKU_APP_H_
#define UI_OZONE_PLATFORM_HAIKU_HAIKU_APP_H_

namespace ui {

// Haiku routes every window through app_server, and app_server will not talk
// to a team that has no BApplication: BWindow's constructor asserts on
// be_app. Chromium's main thread is already a base::MessagePump loop and
// cannot also be a BLooper, so the BApplication gets a thread of its own and
// runs there for the life of the process.
//
// Nothing is dispatched to this application object. It exists so that
// app_server has a team to talk to; the real work happens on the per-window
// threads Haiku creates for each BWindow.
class HaikuApp {
 public:
  // Starts the BApplication thread and waits until be_app is usable. Safe to
  // call more than once; only the first call does anything.
  static void EnsureStarted();

 private:
  HaikuApp() = delete;
};

}  // namespace ui

#endif  // UI_OZONE_PLATFORM_HAIKU_HAIKU_APP_H_
