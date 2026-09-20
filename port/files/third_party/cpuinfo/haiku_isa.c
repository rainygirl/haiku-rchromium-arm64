/* Copyright 2026 The RENKU project
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 *
 * cpuinfo's arm64 initialisation reads /proc/cpuinfo and getauxval(), neither
 * of which Haiku has, so none of src/arm/linux/ is built here. Only the
 * cpuinfo_isa object is actually referenced (through the NEON checks in
 * XNNPACK and friends); leaving every extension off means callers take the
 * baseline paths, which is correct if pessimistic on a CPU that has more.
 */

#include <arm/api.h>

struct cpuinfo_arm_isa cpuinfo_isa = {0};
