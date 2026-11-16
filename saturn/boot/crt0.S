/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Written for the kit from the entry arrangement of avpsaturn v0.1.0-beta, saturn/rt/boot.ld (boot.o(.text.startup) first, so the
 * BIOS's jump to 0x06004000 lands in the loader) and the explicit stack and bss clear of the MvC probe entry.
 *
 * First instruction of the loader image (IP.BIN loads it at 0x06004000 and jumps to its first byte). Masks interrupts, sets the stack,
 * clears bss, calls sat_boot_main(). The link script puts .text.start first (saturn/ld/boot.ld.in).
 * A game that links the SGL system libraries and keeps their own start code does not use this file: boot.ld.in then puts the
 * loader's main in front instead, exactly as the first AvP loader did. */
    .section .text.start,"ax"
    .align 2
    .global _sat_crt0
_sat_crt0:
    mov.l   sr_init,r0
    ldc     r0,sr               ! all interrupts masked
    mov.l   sp_init,r15
    mov.l   bss_s,r1
    mov.l   bss_e,r2
    mov     #0,r0
1:  cmp/hs  r2,r1
    bt      2f
    mov.l   r0,@r1
    bra     1b
    add     #4,r1
2:  mov.l   main_a,r0
    jsr     @r0
    nop
3:  bra     3b
    nop
    .align 2
sr_init: .long 0x000000F0
sp_init: .long _sat_boot_sp          ! provided by the link script (end of the stack area)
bss_s:   .long __bstart
bss_e:   .long __bend
main_a:  .long _sat_boot_main
