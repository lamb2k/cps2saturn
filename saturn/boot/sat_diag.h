/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/rt/boot.c (the "boot display" block, hwboot lane 2026-11-10).
 *
 * Boot display: from the loader's first instruction the screen is ours, with no scroll screen, sprite or SGL.
 * VDP2's back screen in per-line mode shows one band per boot step. A white 2-line tick moves inside the current band while a file loads.
 * The bottom stripes hold a 16 bit value (white = 1, black = 0, most significant bit on top). A failure turns the current band red
 * (CPU exception: magenta) and flashes the whole screen with the code. A console without a debugger shows exactly where it stopped.
 *
 * The runtime reaches the display through a call table (SAT_DIAG_API_ADDR, six words) until its own first picture:
 *   [0] stage(colour, 0)   [1] fatal(code, detail)   [2] done(restore, 0)   [3] active flag
 *   [4] reinit(0, 0)       [5] mark(which, 0), small numbered marks the slave draws
 * and sat_diag_call() below does the null check.
 *
 * What a game supplies: the VDP2 VRAM bytes at SAT_DIAG_TAB_ADDR (last 512 bytes by default) stay clear; and, if its graphics init clears VRAM and
 * the registers, it calls sat_diag_call(SAT_DIAG_REINIT) afterwards and registers sat_diag_restore so "done" can put back the registers the display
 * changed (display mode, back-screen table, access cycles). */
#ifndef SAT_DIAG_H
#define SAT_DIAG_H
#include "../include/sat_hw.h"
#include "../include/sat_cfg.h"

#define SAT_DIAG_API ((volatile unsigned long *)SAT_DIAG_API_ADDR)
enum { SAT_DIAG_STAGE = 0, SAT_DIAG_FATAL = 1, SAT_DIAG_DONE = 2, SAT_DIAG_ACTIVE = 3, SAT_DIAG_REINIT = 4, SAT_DIAG_MARK = 5 };

/* 15 bit colours (BGR). */
#define SAT_C_BLACK 0x0000u
#define SAT_C_GREY 0x4631u
#define SAT_C_RED 0x001fu
#define SAT_C_GREEN 0x03e0u
#define SAT_C_BLUE 0x7c00u
#define SAT_C_YELLOW 0x03ffu
#define SAT_C_CYAN 0x7fe0u
#define SAT_C_MAGENTA 0x7c1fu
#define SAT_C_WHITE 0x7fffu

void sat_diag_init(unsigned tvmd_on);              /* takes the screen and publishes the call table */
void sat_diag_set_tvmd(unsigned tvmd_on);          /* after a clock change: the display mode to show */
void sat_diag_stage(unsigned colour);              /* next band; colour 0 alternates green and blue */
void sat_diag_tick(void);                          /* move the progress tick (call while a file loads) */
void sat_diag_info(unsigned value);                /* the 16 bit stripes */
void sat_diag_reinit(void);                        /* retake the screen after VDP2 was cleared */
void sat_diag_fail(unsigned code, unsigned short colour, unsigned extra) __attribute__((noreturn));
void sat_diag_install_exceptions(void);            /* illegal instruction, slot illegal, address errors: magenta screen, PC in the stripes */
extern void (*sat_diag_restore)(void);             /* game hook: put back registers the display changed (called by done(restore=1)) */

/* From the runtime, through the table: no-op once the display has ended. */
static inline void sat_diag_call(int which, unsigned long a, unsigned long b)
{
    void (*f)(unsigned long, unsigned long) = (void (*)(unsigned long, unsigned long))SAT_DIAG_API[which];
    if (f) f(a, b);
}
#endif
