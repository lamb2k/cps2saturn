/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/gfx/sat_gfx.c (snap_layer, snap_layer_dirty, the drawn_valid / drawn_sN checks in sat_gfx_draw).
 *
 * Unchanged-layer memo. Most frames a scroll layer's visible cells did not change, so the master's first pass over a layer only sums its name
 * words (a cheap multiplicative mix) and copies them to the slave's snapshot only when the sum moved; the slave redraws a layer only when its
 * sum differs from the one it last drew. An unchanged layer costs one pass of reads on the master and nothing on the slave.
 *
 * A game's tile maps run down columns in 64 x 64 name pages. The walk reads along cache lines: for each visible column, the visible rows. row_bits is the
 * log2 of the page height inside one column (the game's map layout: 5 for a 32 row page); (r & low) + ((r & ~low & 63) << 6) is the row's word offset in a column.
 *
 * What a game supplies: the map pointer, the visible window (first column and row, how many of each), and the destination words.
 * The mix is part of the contract between the two CPUs: use SAT_MIX with the same seed on both sides. */
#ifndef SAT_LAYER_H
#define SAT_LAYER_H
#include <stdint.h>

#define SAT_MIX(sum, w) ((((sum) << 5) + (sum)) + (w))
#define SAT_LAYER_MAX_ROWS 32

/* Copies the visible window of a 64 x 64 big endian word map into dest (rows x cols words, row major) if its sum changed.
   Returns the new sum. If dirty is not NULL the copy compares each word with the one it replaces and sets bit `row` of *dirty for each changed row
   (rows <= 32). Pass sum seed = 0 for a fresh layer and `old` = the sum of the last copy; old == new skips the copy. */
uint32_t sat_layer_snapshot(uint32_t *dest, const uint8_t *map, uint32_t xc, uint32_t yc, uint32_t rows, uint32_t cols,
                            uint32_t row_bits, uint32_t sum_seed, uint32_t old, uint32_t *dirty);

typedef struct SatLayerMemo { uint32_t drawn_sum; int valid; } SatLayerMemo;
/* Slave: 1 if the layer must be redrawn for this snapshot sum (and records it), 0 if what is on screen is still right. */
static inline int sat_layer_needs_draw(SatLayerMemo *m, uint32_t sum)
{
    if (m->valid && m->drawn_sum == sum) return 0;
    m->drawn_sum = sum; m->valid = 1;
    return 1;
}
/* A new pack or a forced redraw: every layer is drawn again. */
static inline void sat_layer_invalidate(SatLayerMemo *m) { m->valid = 0; }
#endif
