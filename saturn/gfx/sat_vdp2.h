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
