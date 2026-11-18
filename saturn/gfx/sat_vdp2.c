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

void sat_v2g_init(SatV2Gate *g, SatV2Latch *l, volatile uint16_t *cram, volatile uint8_t *vram, uint32_t gated)
{
    unsigned i;
    g->l = l; g->cram = cram; g->vram = vram; g->gated = gated;
    for (i = 0; i < 2; i++) { g->rser[i] = 0xffffffffu; g->rcq[i] = 0; g->rseq[i] = 0; }
    g->newest = 0xffffffffu; g->applied = 0xffffffffu; g->urg_seen = 0; g->urg_floor = 0;
    g->cq_head = g->cq_tail = g->cq_direct = g->cq_max = g->cq_pub = 0;
    g->nq_head = g->nq_tail = g->nq_pub = g->nq_direct = g->nq_max = 0; g->rnq[0] = g->rnq[1] = 0;
    g->chk_n = g->chk_diff = g->chk_ahead = g->chk_behind = g->chk_last_reg = g->chk_last_shown = 0;
}

static void drain(SatV2Gate *g, uint32_t upto);
static void drain_names(SatV2Gate *g, uint32_t upto);

void sat_v2g_cram(SatV2Gate *g, unsigned entry, unsigned value)
{
    uint32_t h = UNC(g->cq_head), n, spin = 0;
    if (!UNC(g->gated)) { g->cram[entry] = (uint16_t)value; return; }   /* old order: the direct write at draw time */
    while (h - UNC(g->cq_tail) >= SAT_V2G_CRAMQ) {
        if (UNC(g->cq_tail) != UNC(g->cq_pub) && ++spin < SAT_V2G_WAIT) continue;   /* a published picture is pending: the master drains it at its frame change */
        g->cq_direct++; drain(g, h); h = UNC(g->cq_head); break;                    /* one picture alone is more than the queue, or the master never came: write what is queued now, in order (early, as the old order) */
    }
    SAT_UNC16(g->cq_idx[h % SAT_V2G_CRAMQ]) = (uint16_t)entry; SAT_UNC16(g->cq_val[h % SAT_V2G_CRAMQ]) = (uint16_t)value;
    UNC(g->cq_head) = h + 1;
    n = h + 1 - UNC(g->cq_tail);
    if (n > g->cq_max) g->cq_max = n;
}

void sat_v2g_name(SatV2Gate *g, uint32_t addr, uint32_t value)
{
    uint32_t h = UNC(g->nq_head), n, spin = 0;
    if (!UNC(g->gated)) { *(volatile uint32_t *)(void *)(g->vram + addr) = value; return; }   /* old order: the direct write at draw time */
    while (h - UNC(g->nq_tail) >= SAT_V2G_NAMEQ) {
        if (UNC(g->nq_tail) != UNC(g->nq_pub) && ++spin < SAT_V2G_WAIT) continue;
        g->nq_direct++; drain_names(g, h); h = UNC(g->nq_head); break;
    }
    SAT_UNC32(g->nq_addr[h % SAT_V2G_NAMEQ]) = addr; SAT_UNC32(g->nq_val[h % SAT_V2G_NAMEQ]) = value;
    UNC(g->nq_head) = h + 1;
    n = h + 1 - UNC(g->nq_tail);
    if (n > g->nq_max) g->nq_max = n;
}

void sat_v2g_publish(SatV2Gate *g, uint32_t serial)
{
    unsigned i, s = serial & 1u;
    SatV2Latch *l = g->l;
    uint32_t q = UNC(g->rseq[s]);
    UNC(g->rseq[s]) = q + 1;
    for (i = 0; i < SAT_V2L_N; i++) { SAT_UNC16(g->rec[s][i]) = l->wr[i]; SAT_UNC8(g->rv[s][i]) = l->wv[i]; }
    UNC(g->rcq[s]) = UNC(g->cq_head); UNC(g->rnq[s]) = UNC(g->nq_head);
    UNC(g->cq_pub) = UNC(g->cq_head); UNC(g->nq_pub) = UNC(g->nq_head);
    UNC(g->rser[s]) = serial;
    UNC(g->rseq[s]) = q + 2;
    UNC(g->newest) = serial;
}

void sat_v2g_urgent(SatV2Gate *g)
{
    uint32_t n = UNC(g->newest);
    UNC(g->urg_floor) = n == 0xffffffffu ? 0u : n + 1u;
    sat_v2l_publish(g->l);
}

static void drain_names(SatV2Gate *g, uint32_t upto)
{
    uint32_t t = UNC(g->nq_tail);
    while ((int32_t)(upto - t) > 0) { *(volatile uint32_t *)(void *)(g->vram + SAT_UNC32(g->nq_addr[t % SAT_V2G_NAMEQ])) = SAT_UNC32(g->nq_val[t % SAT_V2G_NAMEQ]); t++; }
    UNC(g->nq_tail) = t;
}

static void drain(SatV2Gate *g, uint32_t upto)
{
    uint32_t t = UNC(g->cq_tail);
    while ((int32_t)(upto - t) > 0) { g->cram[SAT_UNC16(g->cq_idx[t % SAT_V2G_CRAMQ])] = SAT_UNC16(g->cq_val[t % SAT_V2G_CRAMQ]); t++; }
    UNC(g->cq_tail) = t;
}

void sat_v2g_apply(SatV2Gate *g, uint32_t shown)
{
    uint32_t want, s, q, i, cq, nq;
    SatV2Latch *l = g->l;
    want = g->gated ? shown : UNC(g->newest);
    if (UNC(l->seq) != g->urg_seen && !(UNC(l->seq) & 1)) { g->urg_seen = UNC(l->seq); sat_v2l_apply(l); }   /* the urgent record, whole state, once; before the picture's record so that a stale one cannot undo it */
    if (want == 0xffffffffu) return;
    s = want & 1u;
    if (UNC(g->rser[s]) != want) return;                    /* not published yet (or replaced by a later picture): tried again at the next V-blank */
    if (g->gated && g->applied == want) return;
    q = UNC(g->rseq[s]);
    if (q & 1u) return;
    for (i = 0; i < SAT_V2L_N; i++) { l->sv[i] = SAT_UNC8(g->rv[s][i]); l->snap[i] = SAT_UNC16(g->rec[s][i]); }
    cq = UNC(g->rcq[s]); nq = UNC(g->rnq[s]);
    if (UNC(g->rseq[s]) != q || UNC(g->rser[s]) != want) return;   /* the slave rewrote the slot during the copy: next V-blank */
    if (want + 1u > UNC(g->urg_floor))
        for (i = 0; i < SAT_V2L_N; i++)
            if (l->sv[i]) l->regs[i] = l->snap[i];
    drain(g, cq); drain_names(g, nq);
    g->applied = want;
}

void sat_v2g_check(SatV2Gate *g, uint32_t started, uint32_t shown)
{
    if (started == 0) return;                               /* nothing plotted through the protocol yet */
    g->chk_n++;
    g->chk_last_reg = g->applied; g->chk_last_shown = shown;
    if (g->applied != shown) {
        g->chk_diff++;
        if (g->applied != 0xffffffffu && (int32_t)(g->applied - shown) > 0) g->chk_ahead++; else g->chk_behind++;
    }
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
