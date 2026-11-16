/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/gfx/sat_gfx.c (lat_publish, lat_apply, lat_reset, the VDP2 block of sat_gfx_init, clear_vram, write_name).
 * See sat_vdp2.h. */
#include "sat_vdp2.h"

#define UNC(x) SAT_UNC32(x)

void sat_v2l_init(SatV2Latch *l, volatile uint16_t *regs)
{
    unsigned i;
    l->regs = regs;
    for (i = 0; i < SAT_V2L_N; i++) { l->wr[i] = 0; l->wv[i] = 0; l->pub[i] = 0; l->pv[i] = 0; l->snap[i] = 0; l->sv[i] = 0; }
    l->seq = 0; l->retries = l->skips = 0; l->mid_copy = 0;
}

void sat_v2l_write(SatV2Latch *l, unsigned off, unsigned val)
{
    l->wr[off >> 1] = (uint16_t)val; l->wv[off >> 1] = 1;
}

void sat_v2l_publish(SatV2Latch *l)
{
    unsigned i;
    uint32_t q = UNC(l->seq);
    UNC(l->seq) = q + 1;
    for (i = 0; i < SAT_V2L_N; i++) { SAT_UNC16(l->pub[i]) = l->wr[i]; SAT_UNC8(l->pv[i]) = l->wv[i]; }
    UNC(l->seq) = q + 2;
}

void sat_v2l_apply(SatV2Latch *l)
{
    unsigned i, t;
    for (t = 0; t < 4; t++) {
        uint32_t q = UNC(l->seq);
        if (q & 1) { l->retries++; continue; }
        for (i = 0; i < SAT_V2L_N; i++) { l->sv[i] = SAT_UNC8(l->pv[i]); l->snap[i] = SAT_UNC16(l->pub[i]); }
        if (l->mid_copy) l->mid_copy(l);
        if (UNC(l->seq) != q) { l->retries++; continue; }
        for (i = 0; i < SAT_V2L_N; i++)
            if (l->sv[i]) l->regs[i] = l->snap[i];
        return;
    }
    l->skips++;
}

void sat_vdp2_layout_apply(volatile uint16_t *r, const SatVdp2Layout *l)
{
    unsigned i;
    r[0x0e / 2] = l->ramctl;
    for (i = 0; i < 8; i++) r[(0x10 + 2 * i) / 2] = l->cyc[i];
    r[0x22 / 2] = 0; r[0x24 / 2] = 0; r[0x26 / 2] = 0;
    r[0x28 / 2] = l->chctla; r[0x2a / 2] = l->chctlb;
    for (i = 0; i < 4; i++) r[(0x30 + 2 * i) / 2] = l->pnc[i];
    r[0x38 / 2] = 0;
    r[0x3a / 2] = l->plsz;
    r[0x3c / 2] = 0;                                   /* map offsets 0 */
    for (i = 0; i < 4; i++) { r[(0x40 + 4 * i) / 2] = l->mpab[i]; r[(0x42 + 4 * i) / 2] = l->mpcd[i]; }
    r[0x72 / 2] = 0; r[0x76 / 2] = 0; r[0x82 / 2] = 0; r[0x86 / 2] = 0;
    r[0x78 / 2] = l->zmx_int[0]; r[0x7a / 2] = l->zmx_dec[0]; r[0x7c / 2] = 1; r[0x7e / 2] = 0;
    r[0x88 / 2] = l->zmx_int[1]; r[0x8a / 2] = l->zmx_dec[1]; r[0x8c / 2] = 1; r[0x8e / 2] = 0;
    r[0x98 / 2] = l->zmctl;
}

void sat_vdp2_set_back(volatile uint16_t *r, uint32_t a)
{
    r[0xac / 2] = (uint16_t)(a >> 17); r[0xae / 2] = (uint16_t)((a >> 1) & 0xffff);
}

void sat_vdp2_clear(volatile uint8_t *vram, uint32_t bytes)
{
    uint32_t i;
    for (i = 0; i < bytes; i += 4) *(volatile uint32_t *)(void *)(vram + i) = 0;
}
