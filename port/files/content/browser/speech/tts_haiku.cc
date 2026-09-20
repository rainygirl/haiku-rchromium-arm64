// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Text-to-speech. Linux talks to speech-dispatcher; Haiku has no equivalent
// service, so this reports "unsupported" the way the Fuchsia implementation
// does -- callers then leave speech synthesis alone instead of crashing.

#include "content/browser/speech/tts_platform_impl.h"

#include <string>

#include "base/functional/callback.h"
#include "base/no_destructor.h"

namespace content {

class TtsPlatformImplHaiku : public TtsPlatformImpl {
 public:
  TtsPlatformImplHaiku() = default;
  TtsPlatformImplHaiku(const TtsPlatformImplHaiku&) = delete;
  TtsPlatformImplHaiku& operator=(const TtsPlatformImplHaiku&) = delete;

  bool PlatformImplSupported() override { return false; }
  bool PlatformImplInitialized() override { return false; }
  void Speak(int utterance_id,
             const std::string& utterance,
             const std::string& lang,
             const VoiceData& voice,
             const UtteranceContinuousParameters& params,
             base::OnceCallback<void(bool)> on_speak_finished) override {
    std::move(on_speak_finished).Run(false);
  }
  bool StopSpeaking() override { return false; }
  void Pause() override {}
  void Resume() override {}
  bool IsSpeaking() override { return false; }
  void GetVoices(std::vector<VoiceData>* out_voices) override {}
  std::string GetError() override { return {}; }
  void ClearError() override {}
  void SetError(const std::string& error) override {}

  static TtsPlatformImplHaiku* GetInstance() {
    static base::NoDestructor<TtsPlatformImplHaiku> tts;
    return tts.get();
  }
};

// static
TtsPlatformImpl* TtsPlatformImpl::GetInstance() {
  return TtsPlatformImplHaiku::GetInstance();
}

}  // namespace content
