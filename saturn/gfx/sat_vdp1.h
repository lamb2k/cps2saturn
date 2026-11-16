/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/gfx/sat_gfx.c (the "VDP1 frame change, safe against a list still plotting" block: sat_gfx_vblank's
 * frame change, plot_wait_end, plot_wait_shown, plot_start, plot_abandon_build; the table setup in sat_gfx_init; lane avp-vanish, 11-08).
 *
 * VDP1 presentation with two alternating command tables and a frame change that is never asked for while a list is still plotting.
 *
 *   The slave builds the next list in the table that is not on show, then starts the plot (PTMR) and counts it in `started`.
 *   The master, first thing in each vblank-in, asks for the frame change (FBCR) only when VDP1 reports the end of that plot (EDSR CEF)
 *   and counts it in `shown`. A list still plotting at a vblank keeps the last whole picture on screen one more frame: a dropped frame,
 *   never a half drawn one. The slave touches the table again only once the last plot is shown.
 *
 * Why it is built this way: emulators forgive a plot that is cut by the frame change and a console shows it. The change shifts the end flag
 * (the current frame's flag becomes the previous one's), so "CEF went clear" is the sign that the change really happened, and waiting for the end of
 * vblank instead raced the emulator's own latch (11 % of pictures went back to an older plot). Timeouts exist for a chip state that was replaced
 * under the code (a save state load): the slave starts the same list again once, then asks for the change itself, then plots anyway, so a lost
 * picture never becomes a stalled slave.
 *
 * Command table layout (VDP1 VRAM): one system clip command at offset 0 jumps to the table in use; each table starts with its local origin at +0x20
 * and the sprite commands from +0x40, ending with the end code (0x8000). Commands are 32 bytes.
 *
 * What a game supplies: the VDP1 VRAM offsets of the two tables (sat_cfg.h SAT_V1_TABLE_A/B, 32 KB apart by default), the screen size, and the command
 * writer (sat_v1_cmd() hands out the base of the table being built). The chip's registers are reached through sat_v1_regs, which a host test can point
 * at an array. */
#ifndef SAT_VDP1_H
#define SAT_VDP1_H
#include "../include/sat_hw.h"
#include "../include/sat_cfg.h"

#define SAT_V1_CMD_BYTES 32u
#define SAT_V1_FIRST_CMD 0x40u        /* offset of the first sprite command inside a table */
#define SAT_V1_END_CODE 0x8000u

typedef struct SatVdp1 {
    volatile uint8_t *vram;            /* VDP1 VRAM */
    volatile uint16_t *regs;           /* VDP1 register file (word indexed) */
    uint32_t table[2];                 /* VRAM offsets of the two tables */
    uint32_t cur;                      /* index of the table being built */
    uint32_t started, shown, held;     /* shared between the CPUs, accessed through the uncached alias */
    uint32_t sync;                     /* the master's first vblank hook has run: the synchronized path is on */
    uint32_t waits;                    /* frames the master held the last picture because VDP1 had not finished (diagnostic) */
    uint32_t cef_asked, cef_forced, replots;   /* stuck end-flag recoveries (diagnostic) */
    uint32_t kicked;                   /* serial of the plot already started again once */
    uint32_t wait_max;                 /* slave FRT ticks to wait at each step */
    uint32_t (*ticks)(void);           /* the slave's timer; the host test supplies a counter */
    int prev;                          /* a plot has been submitted before (the first plot has no earlier change to latch) */
} SatVdp1;

/* Clears the tables' heads and starts with table 0. screen_w/h is the system clip. Does not touch the display mode. */
void sat_v1_init(SatVdp1 *v, volatile uint8_t *vram, volatile uint16_t *regs, uint32_t table_a, uint32_t table_b,
                 unsigned screen_w, unsigned screen_h, uint32_t (*ticks)(void));
/* VRAM address of the first sprite command of the table being built. The caller writes commands from there and ends the list with sat_v1_end(). */
volatile uint8_t *sat_v1_cmd(SatVdp1 *v);
void sat_v1_end(SatVdp1 *v, volatile uint8_t *after_last);

/* Master, first thing in the vblank-in handler (after the display registers are applied). Asks for the change if the last plot ended. */
void sat_v1_vblank(SatVdp1 *v);

/* Slave, before touching the table or any texture slot: wait for the last plot to end. 0 = timed out: abandon this build and keep the game going. */
int sat_v1_wait_end(SatVdp1 *v);
/* Slave, after the list is built: start the plot. 1 plotted, 0 the change was never confirmed (the caller restores its texture protection). */
int sat_v1_plot(SatVdp1 *v);
#endif
