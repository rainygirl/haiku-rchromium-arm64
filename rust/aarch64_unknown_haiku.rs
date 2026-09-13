use crate::spec::{Arch, StackProbeType, Target, TargetMetadata, TargetOptions, base};

pub(crate) fn target() -> Target {
    Target {
        llvm_target: "aarch64-unknown-haiku".into(),
        metadata: TargetMetadata {
            description: Some("ARM64 Haiku".into()),
            tier: Some(3),
            host_tools: Some(false),
            std: Some(true),
        },
        pointer_width: 64,
        data_layout: "e-m:e-p270:32:32-p271:32:32-p272:64:64-i8:8:32-i16:16:32-i64:64-i128:128-n32:64-S128-Fn32".into(),
        arch: Arch::AArch64,
        options: TargetOptions {
            features: "+v8a".into(),
            max_atomic_width: Some(128),
            stack_probes: StackProbeType::Inline,
            // Haiku executables are ET_DYN and the runtime loader expects
            // position-independent code, the same as on x86_64 Haiku.
            position_independent_executables: true,
            ..base::haiku::opts()
        },
    }
}
