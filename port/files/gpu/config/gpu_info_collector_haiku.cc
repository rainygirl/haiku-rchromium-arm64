// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// GPU information. Haiku has no GL and this port runs the compositor in
// software, so there is nothing to collect: report the failure the collectors
// already have a code for, which leaves the GPU as "software only" rather
// than claiming capabilities that are not there.

#include "gpu/config/gpu_info_collector.h"

namespace gpu {

bool CollectContextGraphicsInfo(GPUInfo* gpu_info) {
  return false;
}

bool CollectBasicGraphicsInfo(GPUInfo* gpu_info) {
  return false;
}

}  // namespace gpu
