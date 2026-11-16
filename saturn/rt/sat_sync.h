/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/rt/kernel.c (slave_start, sat_slave_main, the hand-off at the top of sat_vblank, irq_enable) and
 * saturn/gfx/sat_gfx.h (the snapshot halves).
 *
 * Two SH-2s, one picture at a time. The master runs the game. At each vblank-in it hands the slave a snapshot of what drawing needs;
 * the slave builds the VDP1 command list, uploads textures and writes the VDP2 layers; the master never waits for it.
 *
 *   master, in its vblank handler        sat_sync_vblank_begin();                      re-arm the SCU, restart the timer
 *                                        if (sat_sync_try_handoff(begin, layers)) ...  a slave still drawing skips this picture, never the game
 *   slave, forever                       sat_sync_slave_loop(draw);
 *
 * try_handoff does, only when the slave has finished the last picture: begin() (the master copies what the slave needs and nothing else
 * touches), then counts the picture and wakes the slave, then layers() (the long second half of the snapshot, copied while the slave builds
 * the sprite commands). The slave waits for the game's own flag before it reads a layer word (sat_sync_snapshot_ready below).
 * The two counters are read and written through the cache-through alias; the draw function runs with the slave's cache on.
 *
 * What a game supplies: sat_slave_main() (calls sat_sync_slave_loop with its draw function), sat_vblank() (calls the pieces above), sat_main().
 * Stack sizes and the slave wait bound are in sat_cfg.h. */
#ifndef SAT_SYNC_H
#define SAT_SYNC_H
#include "../include/sat_hw.h"
#include "../include/sat_cfg.h"

extern uint32_t sat_gfx_handed, sat_gfx_done;    /* pictures handed to the slave / finished by it; equal means the slave is idle */
extern uint32_t sat_gfx_skips;                   /* vblanks that found the slave still busy */
extern uint32_t sat_slave_stack[];               /* SAT_SLAVE_STACK_WORDS words */

/* Master: vector table, SCU mask, then interrupts on. vblank_out may be NULL (only vblank-in is enabled then). */
void sat_sync_irq_install(void (*vblank_in_entry)(void), void (*vblank_out_entry)(void));
/* Master, first thing in the vblank-in handler. The SCU sets its whole interrupt mask when the CPU takes an interrupt (so handlers do not
   nest); the handler must put its mask back or no further interrupt arrives (the game stopped after the first picture on cores that model it). */
void sat_sync_vblank_begin(void);
void sat_sync_timer_reset(void);                 /* master FRT to zero (free running timer, phi/128, about 4.5 us a tick) */

int sat_sync_slave_idle(void);                   /* nonzero: the last picture is finished */
int sat_sync_try_handoff(void (*begin)(void), void (*layers)(void));
/* Master: wait until the slave is idle, with interrupts as they are. For a restart or a long disc load. */
void sat_sync_wait_idle(void);

/* Switch the slave on through the SMPC (SSHON) with its entry and stack from this module. entry is _sat_slave_entry (sat_ctx.S). */
void sat_sync_slave_start(void);
/* The slave's main: wake on the FRT input capture, run draw() for each picture handed over, mark it done. Never returns.
   ticks_out (optional) receives the slave's FRT ticks of the last picture. */
void sat_sync_slave_loop(void (*draw)(void), volatile uint32_t *ticks_out);

/* Layer words the master copies after the hand-off: the master sets the flag when the copy is whole, the slave waits for it. */
void sat_sync_snapshot_clear(volatile uint32_t *flag);
void sat_sync_snapshot_set(volatile uint32_t *flag);
void sat_sync_snapshot_wait(volatile uint32_t *flag);

/* Task and IRQ stack tops, read by sat_ctx.S. */
extern uint32_t sat_boot_sp_var, sat_irq_sp, sat_slave_sp;
#endif
