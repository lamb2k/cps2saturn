/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/rt/pad.c (sat_pad_tick). The AvP input latch mapping (map_pad), the scripted input test hooks and the
 * home-menu second-port remap stayed behind. See sat_pad.h. */
#include "sat_pad.h"
#include "../include/sat_hw.h"

uint32_t sat_pad_raw = 0xffff, sat_pad_raw2 = 0xffff;

#define SF_OFF 0x63
#define SR_OFF 0x61
#define COM_OFF 0x1f
#define IREG_OFF(n) (1 + (n) * 2)
#define OREG_OFF(n) (0x21 + (n) * 2)

void sat_pad_tick_ops(const SatSmpcOps *o)
{
    if (!(o->rd(o->ctx, SF_OFF) & 1)) {
        uint32_t st = o->rd(o->ctx, OREG_OFF(0)), id = o->rd(o->ctx, OREG_OFF(1));
        if (st == 0xf1 && (id >> 4) == 0) sat_pad_raw = ((uint32_t)o->rd(o->ctx, OREG_OFF(2)) << 8) | o->rd(o->ctx, OREG_OFF(3));
        else if (st == 0xf0) sat_pad_raw = 0xffff;
        if (st == 0xf1 && (id >> 4) == 0 && o->rd(o->ctx, OREG_OFF(4)) == 0xf1 && (o->rd(o->ctx, OREG_OFF(5)) >> 4) == 0)
            sat_pad_raw2 = ((uint32_t)o->rd(o->ctx, OREG_OFF(6)) << 8) | o->rd(o->ctx, OREG_OFF(7));
        else sat_pad_raw2 = 0xffff;
        if (o->rd(o->ctx, SR_OFF) & 0x20) {            /* more ports queued: drop them */
            o->wr(o->ctx, IREG_OFF(0), 0x40);
            o->wr(o->ctx, SF_OFF, 1);
        } else {
            o->wr(o->ctx, IREG_OFF(0), 0x00);          /* no SMPC status report */
            o->wr(o->ctx, IREG_OFF(1), 0x0a);          /* peripheral data wanted (the values AvP ran on a console) */
            o->wr(o->ctx, IREG_OFF(2), 0xf0);
            o->wr(o->ctx, SF_OFF, 1);                  /* SF first, then the command: the command clears SF when it ends */
            o->wr(o->ctx, COM_OFF, 0x10);
        }
    }
}

#ifndef SAT_HOST
static uint8_t hw_rd(void *ctx, unsigned off) { (void)ctx; return SAT_SMPC(off); }
static void hw_wr(void *ctx, unsigned off, uint8_t v) { (void)ctx; SAT_SMPC(off) = v; }
void sat_pad_tick(void)
{
    static const SatSmpcOps hw = { hw_rd, hw_wr, 0 };
    sat_pad_tick_ops(&hw);
}
#endif

uint32_t sat_pad_map(uint32_t raw, const SatPadMap *map, unsigned n, uint32_t idle_value, int active_low_out)
{
    uint32_t v = idle_value;
    unsigned i;
    for (i = 0; i < n; i++)
        if (!(raw & map[i].saturn_mask)) { if (active_low_out) v &= ~(uint32_t)map[i].game_mask; else v |= map[i].game_mask; }
    return v;
}
