/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Range store lookup written for the kit (the flat accessors in sat_opx.h are moved from avpsaturn v0.1.0-beta, saturn/rt/lift_target.h). See sat_opx.h. */
#include "sat_opx.h"

static uint32_t be32(const uint8_t *p) { return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3]; }
static uint32_t be16(const uint8_t *p) { return ((uint32_t)p[0] << 8) | p[1]; }

void sat_opx_init(SatOpx *x, const void *store, const void *data_view)
{
    x->store = (const uint8_t *)store; x->data_view = (const uint8_t *)data_view; x->miss = 0; x->misses = 0;
}

const uint8_t *sat_opx_find(SatOpx *x, uint32_t a)
{
    int32_t lo = 0, hi = (int32_t)be32(x->store) - 1;
    while (lo <= hi) {
        int32_t m = (lo + hi) >> 1;
        const uint8_t *e = x->store + 4 + 12 * (uint32_t)m;
        uint32_t st = be32(e), n = be32(e + 4);
        if (a < st) hi = m - 1; else if (a >= st + n) lo = m + 1; else return x->store + be32(e + 8) + (a - st);
    }
    x->miss = a; x->misses++;
    return 0;
}
uint32_t sat_opx8(SatOpx *x, uint32_t a) { const uint8_t *p = sat_opx_find(x, a); return p ? *p : x->data_view[a]; }
uint32_t sat_opx16(SatOpx *x, uint32_t a) { const uint8_t *p = sat_opx_find(x, a); return p ? be16(p) : be16(x->data_view + a); }
uint32_t sat_opx32(SatOpx *x, uint32_t a) { const uint8_t *p = sat_opx_find(x, a); return p ? be32(p) : be32(x->data_view + a); }
