/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/gfx/sat_gfx.c (snap_layer, snap_layer_dirty). See sat_layer.h. */
#include "sat_layer.h"

static inline uint32_t rd32be(const uint8_t *p)
{
#if defined(__sh__)
    return *(const uint32_t *)(const void *)p;   /* big endian, map words are 4 byte aligned */
#else
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
#endif
}

uint32_t sat_layer_snapshot(uint32_t *dest, const uint8_t *map, uint32_t xc, uint32_t yc, uint32_t rows, uint32_t cols,
                            uint32_t row_bits, uint32_t sum, uint32_t old, uint32_t *dirty)
{
    uint32_t row_off[SAT_LAYER_MAX_ROWS], col, row, low = (1u << row_bits) - 1, dm = 0;
    if (rows > SAT_LAYER_MAX_ROWS) rows = SAT_LAYER_MAX_ROWS;
    for (row = 0; row < rows; row++) {
        uint32_t r = (yc + row) & 63;
        row_off[row] = ((r & low) + ((r & (63u & ~low)) << 6)) * 4;
    }
    for (col = 0; col < cols; col++) {
        const uint8_t *base = map + ((((xc + col) & 63) << row_bits) * 4);
        for (row = 0; row < rows; row++) sum = SAT_MIX(sum, rd32be(base + row_off[row]));
    }
    if (sum == old) return sum;
    for (col = 0; col < cols; col++) {
        const uint8_t *base = map + ((((xc + col) & 63) << row_bits) * 4);
        uint32_t *cell = dest + col, bit = 1;
        for (row = 0; row < rows; row++, cell += cols, bit <<= 1) {
            uint32_t v = rd32be(base + row_off[row]);
            if (dirty) { if (*cell != v) { *cell = v; dm |= bit; } }
            else *cell = v;
        }
    }
    if (dirty) *dirty |= dm;
    return sum;
}
