! SPDX-License-Identifier: MIT
! Copyright (c) 2026 lamb2k and cps2saturn contributors
! Moved from avpsaturn v0.1.0-beta, saturn/rt/ctx.s. Changes: the stack tops come from C variables (sat_sync.c) so sizes are configuration,
! r14 (the lifted game's CPU record pointer in AvP) is optional (-DSAT_R14_SYMBOL=_name), the PC sampler stub stayed behind.
!
! Entry points of the runtime:
!   _sat_start         the runtime's first instruction (the loader jumps here through SAT_BOOT_ENTRY): own stack, then sat_main()
!   _sat_slave_entry   the slave SH-2 starts here (the BIOS reads its address from 0x06000250): interrupts masked, own stack, sat_slave_main()
!   _sat_switch        void sat_switch(void **save_sp, void *load_sp): coroutine switch, callee-saved registers only
!   _sat_vblank_entry  SCU vblank-in vector: saves the caller-saved registers, switches to the IRQ stack, calls sat_vblank(), returns with rte
!   _sat_exc_illegal / _sat_exc_slot / _sat_exc_addr   CPU exception stubs: call sat_exception(vector, pc, pr)
! A game supplies the C functions sat_main, sat_slave_main, sat_vblank, sat_exception.
    .text
    .align 2
    .global _sat_start
_sat_start:
    mov.l   .Lboot_sp,r0
    mov.l   @r0,r15
#ifdef SAT_R14_SYMBOL
    mov.l   .Lr14,r14
#endif
    mov.l   .Lmain,r0
    jsr     @r0
    nop
1:  bra     1b
    nop

    .global _sat_slave_entry
_sat_slave_entry:
    mov     #-16,r0
    extu.b  r0,r0
    ldc     r0,sr
    mov.l   .Lslave_sp,r0
    mov.l   @r0,r15
#ifdef SAT_R14_SYMBOL
    mov.l   .Lr14,r14
#endif
    mov.l   .Lslave,r0
    jmp     @r0
    nop

    .global _sat_switch
_sat_switch:
    sts.l   pr,@-r15
    mov.l   r13,@-r15
    mov.l   r12,@-r15
    mov.l   r11,@-r15
    mov.l   r10,@-r15
    mov.l   r9,@-r15
    mov.l   r8,@-r15
    mov.l   r15,@r4
    mov     r5,r15
    mov.l   @r15+,r8
    mov.l   @r15+,r9
    mov.l   @r15+,r10
    mov.l   @r15+,r11
    mov.l   @r15+,r12
    mov.l   @r15+,r13
    lds.l   @r15+,pr
    rts
    nop

! System libraries can hold r14 when the IRQ lands, so a game that keeps global state behind r14 has it reloaded here.
    .global _sat_vblank_entry
_sat_vblank_entry:
    mov.l   r14,@-r15
    mov.l   r0,@-r15
    mov.l   r1,@-r15
    mov.l   r2,@-r15
    mov.l   r3,@-r15
    mov.l   r4,@-r15
    mov.l   r5,@-r15
    mov.l   r6,@-r15
    mov.l   r7,@-r15
    mov.l   r8,@-r15
    sts.l   mach,@-r15
    sts.l   macl,@-r15
    sts.l   pr,@-r15
    mov     r15,r8
    mov.l   .Lirq_sp,r0
    mov.l   @r0,r15
#ifdef SAT_R14_SYMBOL
    mov.l   .Lr14,r14
#endif
    mov.l   .Lvblank,r0
    jsr     @r0
    nop
    mov     r8,r15
    lds.l   @r15+,pr
    lds.l   @r15+,macl
    lds.l   @r15+,mach
    mov.l   @r15+,r8
    mov.l   @r15+,r7
    mov.l   @r15+,r6
    mov.l   @r15+,r5
    mov.l   @r15+,r4
    mov.l   @r15+,r3
    mov.l   @r15+,r2
    mov.l   @r15+,r1
    mov.l   @r15+,r0
    mov.l   @r15+,r14
    rte
    nop

    .global _sat_exc_illegal
    .global _sat_exc_slot
    .global _sat_exc_addr
_sat_exc_illegal:
    bra     .Lexc
    mov     #4,r4
_sat_exc_slot:
    bra     .Lexc
    mov     #6,r4
_sat_exc_addr:
    mov     #9,r4
.Lexc:
    mov.l   @r15,r5
    sts     pr,r6
#ifdef SAT_R14_SYMBOL
    mov.l   .Lr14,r14
#endif
    mov.l   .Lexcc,r0
    jmp     @r0
    nop
    .align 2
.Lslave_sp: .long _sat_slave_sp
.Lboot_sp:  .long _sat_boot_sp_var
.Lirq_sp:   .long _sat_irq_sp
.Lslave:    .long _sat_slave_main
.Lexcc:     .long _sat_exception
.Lmain:     .long _sat_main
.Lvblank:   .long _sat_vblank
#ifdef SAT_R14_SYMBOL
.Lr14:      .long SAT_R14_SYMBOL
#endif
