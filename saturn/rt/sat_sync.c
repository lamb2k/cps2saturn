/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/rt/kernel.c (slave_start, sat_slave_main, sat_vblank's hand-off, irq_enable). See sat_sync.h. */
#include "sat_sync.h"

#ifndef SAT_IRQ_STACK_BYTES
#define SAT_IRQ_STACK_BYTES 8192
#endif
#ifndef SAT_RT_STACK_BYTES
#define SAT_RT_STACK_BYTES 8192
#endif
#ifdef SAT_HOST
#define SAT_STACK_SECTION
#else
#ifndef SAT_STACK_SECTION
#define SAT_STACK_SECTION __attribute__((section(".hwstack")))
#endif
#endif

uint32_t sat_gfx_handed, sat_gfx_done, sat_gfx_skips;
uint32_t sat_slave_stack[SAT_SLAVE_STACK_WORDS] __attribute__((aligned(4))) SAT_STACK_SECTION;
static uint8_t sat_irq_stack[SAT_IRQ_STACK_BYTES] __attribute__((aligned(4), unused)) SAT_STACK_SECTION;
static uint8_t sat_rt_stack[SAT_RT_STACK_BYTES] __attribute__((aligned(4), unused)) SAT_STACK_SECTION;
#ifdef SAT_HOST   /* a 64 bit host cannot hold a stack address in 32 bits; the stack tops are only read by sat_ctx.S */
uint32_t sat_boot_sp_var, sat_irq_sp, sat_slave_sp;
#else
uint32_t sat_boot_sp_var = (uint32_t)(uintptr_t)(sat_rt_stack + SAT_RT_STACK_BYTES);
uint32_t sat_irq_sp = (uint32_t)(uintptr_t)(sat_irq_stack + SAT_IRQ_STACK_BYTES);
uint32_t sat_slave_sp = (uint32_t)(uintptr_t)(sat_slave_stack + SAT_SLAVE_STACK_WORDS);
#endif

#ifndef SAT_HOST
static uint32_t ims_mask = 0xfffffffeu;

void sat_sync_irq_install(void (*vblank_in_entry)(void), void (*vblank_out_entry)(void))
{
    uint32_t vbr = 0x06000000u;
    __asm__ volatile ("ldc %0,sr" : : "r"(0xf0));
    SAT_VECTOR_BASE[SAT_VEC_VBLANK_IN] = vblank_in_entry;
    if (vblank_out_entry) SAT_VECTOR_BASE[SAT_VEC_VBLANK_OUT] = vblank_out_entry;
    __asm__ volatile ("ldc %0,vbr" : : "r"(vbr));
    SAT_SCU32(SAT_SCU_IST) = 0;                         /* clear pending */
    ims_mask = vblank_out_entry ? 0xfffffffcu : 0xfffffffeu;
    SAT_SCU32(SAT_SCU_IMS) = ims_mask;
    __asm__ volatile ("ldc %0,sr" : : "r"(0x00));
}
void sat_sync_vblank_begin(void)
{
    SAT_SCU32(SAT_SCU_IST) = ~SAT_IRQ_VBLANK_IN;
    SAT_SCU32(SAT_SCU_IMS) = ims_mask;
}
void sat_sync_timer_reset(void) { SAT_FRTH = 0; SAT_FRTL = 0; }

/* The SMPC is busy while SF is set (the BIOS polls it every frame): a bounded wait, never a spin. */
static void __attribute__((noinline)) smpc_idle(void)
{
    uint32_t n;
    for (n = 0; n < 4000000u && (SAT_SMPC_SF & 1); n++) ;
}
extern void sat_slave_entry(void);
void sat_sync_slave_start(void)
{
    smpc_idle();
    SAT_SMPC_SF = 1; SAT_SMPC_COMREG = SAT_SMPC_SSHOFF;
    smpc_idle();
    *SAT_BIOS_SLAVE_ENTRY = sat_slave_entry;
    *SAT_BIOS_SLAVE_STACK = (uint32_t)(uintptr_t)(sat_slave_stack + SAT_SLAVE_STACK_WORDS);
    SAT_SMPC_SF = 1; SAT_SMPC_COMREG = SAT_SMPC_SSHON;
    smpc_idle();
}
void sat_sync_slave_loop(void (*draw)(void), volatile uint32_t *ticks_out)
{
    SAT_CCR = 0x10; SAT_CCR = 0x01;     /* purge, then cache on */
    SAT_FTCR = 2;
    for (;;) {
        uint32_t seen;
        while (!(SAT_FTCSR & SAT_FTCSR_ICF)) ;
        SAT_FTCSR = (uint8_t)(SAT_FTCSR & 0x7f);
        SAT_CCR = 0x11;                 /* purge again with the cache on: the master wrote the snapshot behind this CPU's cache */
        seen = SAT_UNC32(sat_gfx_handed);
        if (seen == SAT_UNC32(sat_gfx_done)) continue;
        SAT_FRTH = 0; SAT_FRTL = 0;
        draw();
        if (ticks_out) *ticks_out = sat_frt();
        SAT_UNC32(sat_gfx_done) = seen;
    }
}
void sat_sync_wait_idle(void) { while (SAT_UNC32(sat_gfx_done) != SAT_UNC32(sat_gfx_handed)) ; }
int sat_sync_try_handoff(void (*begin)(void), void (*layers)(void))
{
    if (SAT_UNC32(sat_gfx_done) != SAT_UNC32(sat_gfx_handed)) { sat_gfx_skips++; return 0; }
    if (begin) begin();
    SAT_UNC32(sat_gfx_handed) = SAT_UNC32(sat_gfx_handed) + 1;
    SAT_SLAVE_WAKE = 0xffff;
    if (layers) layers();
    return 1;
}
#else
void sat_sync_wait_idle(void) {}
int sat_sync_try_handoff(void (*begin)(void), void (*layers)(void))
{
    if (SAT_UNC32(sat_gfx_done) != SAT_UNC32(sat_gfx_handed)) { sat_gfx_skips++; return 0; }
    if (begin) begin();
    SAT_UNC32(sat_gfx_handed) = SAT_UNC32(sat_gfx_handed) + 1;
    if (layers) layers();
    return 1;
}
#endif
int sat_sync_slave_idle(void) { return SAT_UNC32(sat_gfx_done) == SAT_UNC32(sat_gfx_handed); }
void sat_sync_snapshot_clear(volatile uint32_t *flag) { *(volatile uint32_t *)SAT_UNC(flag) = 0; }
void sat_sync_snapshot_set(volatile uint32_t *flag) { SAT_BARRIER(); *(volatile uint32_t *)SAT_UNC(flag) = 1; }
void sat_sync_snapshot_wait(volatile uint32_t *flag)
{
    while (!*(volatile uint32_t *)SAT_UNC(flag)) ;
    SAT_BARRIER();
}
