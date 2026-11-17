/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/gfx/sat_gfx.c (the VDP2 latch, "lat_*", and the register block of sat_gfx_init).
 *
 * VDP2 set-up, the register latch, and the per-cell write memo.
 *
 * LATCH. Display registers written while a picture is drawn go through a latch and reach the chip at V-blank IN (SGL's rule: the display registers
 * are set in the V-blank). The slave draws at any beam position: a scroll register written mid frame is taken at the next line, and a vertical
 * scroll write of NBG2 or NBG3 restarts that layer's vertical coordinate at that very line (a doubled HUD on the console). So the slave records its
 * writes (sat_v2l_write) and publishes them as a whole at the end of the picture (sequence word odd while it copies, even when complete); the master
 * applies the last complete record at V-blank IN. The apply copies the record first and checks the sequence word before and after, so a vblank
 * never writes registers from two different pictures, and an interrupted copy writes nothing.
 *
 * LAYOUT. One struct holds every register the access cycle rules depend on (RAMCTL, cycles, character control, name control, plane size, map
 * addresses, zoom), written together, so the cycle checker can read the same numbers the console gets.
 *
 * What a game supplies: the register values (SatVdp2Layout), which registers its draw writes (everything below SAT_V2L_N words is latched). */
#ifndef SAT_VDP2_H
#define SAT_VDP2_H
#include "../include/sat_hw.h"

#define SAT_V2L_N 0x88   /* registers 0x00 to 0x10e, one slot per word */

typedef struct SatV2Latch {
    volatile uint16_t *regs;       /* the register file; SAT_VDP2_REG's base on a console */
    uint16_t wr[SAT_V2L_N];        /* the slave's pending writes */
    uint8_t wv[SAT_V2L_N];
    uint16_t pub[SAT_V2L_N];       /* the published record */
    uint8_t pv[SAT_V2L_N];
    uint16_t snap[SAT_V2L_N];      /* the master's copy */
    uint8_t sv[SAT_V2L_N];
    uint32_t seq;                  /* odd while a publish is copying */
    uint32_t retries, skips;       /* records re-read because one was published during the apply; vblanks that found one mid-publish four times */
    void (*mid_copy)(struct SatV2Latch *); /* test hook: runs between the master's copy and its re-check; NULL in a game */
} SatV2Latch;

void sat_v2l_init(SatV2Latch *l, volatile uint16_t *regs);
void sat_v2l_write(SatV2Latch *l, unsigned byte_offset, unsigned value);   /* slave, while drawing */
void sat_v2l_publish(SatV2Latch *l);                                       /* slave, once, when the picture's registers are all written */
void sat_v2l_apply(SatV2Latch *l);                                         /* master, first thing at V-blank IN */

/* ---- picture gated apply (lane vsync) ----
   The latch above applies the newest published record at the first V-blank after the slave publishes it. The slave publishes right after it starts a VDP1 plot, but the frame change
   for that picture comes at a later V-blank (when the plot has ended, and after the display hold), so the scroll layers can show picture N while the sprites still show N-1.
   The gate ties both to one serial: the slave publishes a record for serial s (the number the kit's sat_v1_plot will have started: v1.started + 1 while it builds, v1.started after the
   plot), the master applies the record whose serial is the picture VDP1 has just shown (v1.shown). Two record slots (serial & 1) are enough: the slave starts plot s + 2 only after
   s + 1 was shown, and s was applied at its own change. Colour RAM writes the slave makes while building a picture go through a queue (sat_v2g_cram) and are written by the master
   with the same record. gated = 0 gives the old order (newest record at the next V-blank), for A/B. Records carry the full register state (the writer accumulates every register ever written),
   so a record that is skipped loses nothing. */
#define SAT_V2G_CRAMQ 2048   /* queued colour RAM writes (entries); a full queue makes the writer wait for the master, then write directly (counted) */
typedef struct SatV2Gate {
    SatV2Latch *l;                       /* its wr/wv are the writer's pending registers, its pub/pv/seq the urgent record */
    uint16_t rec[2][SAT_V2L_N];
    uint8_t rv[2][SAT_V2L_N];
    uint32_t rser[2];                    /* serial each slot holds, 0xffffffff = none */
    uint32_t rcq[2];                     /* colour queue head at publish */
    uint32_t rseq[2];                    /* odd while the slot is being written */
    uint32_t newest;                     /* serial of the last publish */
    uint32_t applied;                    /* serial of the record the registers hold (0xffffffff = none yet) */
    uint32_t urg_seen;                   /* l->seq already applied by the urgent record */
    uint32_t urg_floor;                  /* serial + 1 of the newest record published before the urgent one (0 none): such a record's registers are not applied, the urgent state stands */
    uint32_t gated;                      /* 1 apply at the frame change of the same picture, 0 apply the newest record at the next V-blank (old order) */
    volatile uint16_t *cram;             /* colour RAM base, or the host's array */
    uint32_t cq_head, cq_tail;           /* queue positions (counts, not indexes) */
    uint16_t cq_idx[SAT_V2G_CRAMQ], cq_val[SAT_V2G_CRAMQ];
    uint32_t cq_direct;                  /* writes that found the queue full and went straight to colour RAM */
    uint32_t cq_max;                     /* most entries ever pending */
    uint32_t chk_n, chk_diff, chk_ahead, chk_behind;   /* per V-blank check: pictures the registers belong to against the picture VDP1 shows */
    uint32_t chk_last_reg, chk_last_shown;
} SatV2Gate;
void sat_v2g_init(SatV2Gate *g, SatV2Latch *l, volatile uint16_t *cram, uint32_t gated);
void sat_v2g_publish(SatV2Gate *g, uint32_t serial);                 /* slave: the record (all registers written so far) and the colour queue so far belong to this picture */
void sat_v2g_urgent(SatV2Gate *g);                                   /* slave: apply the pending registers at the next V-blank whatever the picture (layers off while a pack loads) */
void sat_v2g_cram(SatV2Gate *g, unsigned entry, unsigned value);   /* slave: a colour RAM write that belongs to the picture being built */
void sat_v2g_apply(SatV2Gate *g, uint32_t shown);                    /* master, first thing at V-blank IN, after sat_v1_vblank so that shown is this V-blank's */
void sat_v2g_check(SatV2Gate *g, uint32_t started, uint32_t shown);  /* master, last: counts the V-blank as a difference when the applied record is not the shown picture's */

typedef struct SatVdp2Layout {
    uint16_t ramctl;               /* 0x0e */
    uint16_t cyc[8];               /* 0x10..0x1e: A0L A0U A1L A1U B0L B0U B1L B1U */
    uint16_t chctla, chctlb;       /* 0x28, 0x2a */
    uint16_t pnc[4];               /* 0x30..0x36 */
    uint16_t plsz;                 /* 0x3a */
    uint16_t mpab[4], mpcd[4];     /* 0x40..0x4e, planes A/B and C/D of NBG0..3 */
    uint16_t zmctl;                /* 0x98 */
    uint16_t zmx_int[2], zmx_dec[2]; /* NBG0 and NBG1 horizontal zoom increment (0x78, 0x7a, 0x88, 0x8a); 1 and 0 = 1:1 */
} SatVdp2Layout;
void sat_vdp2_layout_apply(volatile uint16_t *regs, const SatVdp2Layout *l);
/* Back screen colour at a VRAM byte address (0x1fffe for the last word of bank A0's first 128 KB, as AvP). */
void sat_vdp2_set_back(volatile uint16_t *regs, uint32_t vram_addr);
void sat_vdp2_clear(volatile uint8_t *vram, uint32_t bytes);   /* long writes; bytes a multiple of 4 */

/* Write a 32 bit name or row word only when it changed. shadow keeps what the VRAM holds, so an unchanged cell costs one compare and no bus write.
   Returns 1 if it wrote. */
static inline int sat_shadow_write32(volatile uint8_t *addr, uint32_t value, uint32_t *shadow)
{
    if (*shadow == value) return 0;
    *shadow = value;
    *(volatile uint32_t *)(void *)addr = value;
    return 1;
}
#endif
