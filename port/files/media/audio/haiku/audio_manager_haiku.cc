// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <memory>

#include "media/audio/fake_audio_manager.h"

// Haiku's audio goes through the Media Kit: BSoundPlayer for output and
// BMediaRoster for enumeration and input. Neither is wired up yet, and an
// AudioManager backed by them is a piece of work in its own right -- the Media
// Kit runs its own server and its own threads, and the buffer handoff has to
// be bridged onto Chrome's audio thread.
//
// Until that exists this returns the fake manager, which is the same thing the
// Linux file falls back to when neither ALSA nor PulseAudio is available. It
// produces silence with correct timing, so playback reports progress and ends
// when it should, rather than the renderer stalling on an audio sink that
// never drains.

namespace media {

std::unique_ptr<media::AudioManager> CreateAudioManager(
    std::unique_ptr<AudioThread> audio_thread,
    AudioLogFactory* audio_log_factory) {
  return std::make_unique<FakeAudioManager>(std::move(audio_thread),
                                            audio_log_factory);
}

}  // namespace media
