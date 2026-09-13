use crate::prelude::*;

s! {
    // Haiku's struct vregs, from headers/posix/arch/arm64/signal.h:
    //
    //   struct vregs {
    //       ulong       x[30];
    //       ulong       lr;
    //       ulong       sp;
    //       ulong       elr;
    //       ulong       spsr;
    //       __uint128_t fp_q[32];
    //       u_int       fpsr;
    //       u_int       fpcr;
    //   };
    //
    // signal.h then does `typedef struct vregs mcontext_t;`, so unlike the
    // x86_64 target there is no separate register/FPU split to mirror.
    pub struct mcontext_t {
        pub x: [c_ulong; 30],
        pub lr: c_ulong,
        pub sp: c_ulong,
        pub elr: c_ulong,
        pub spsr: c_ulong,
        pub fp_q: [u128; 32],
        pub fpsr: c_uint,
        pub fpcr: c_uint,
    }

    pub struct ucontext_t {
        pub uc_link: *mut ucontext_t,
        pub uc_sigmask: crate::sigset_t,
        pub uc_stack: crate::stack_t,
        pub uc_mcontext: mcontext_t,
    }
}
