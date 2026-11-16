/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/gfx/sat_gfx.c (Cache, cache_find, cache_get, cache_frame, the blank-tile memo).
 *
 * A tile cache over a block of VRAM that holds fixed size slots: sprite textures in VDP1 VRAM, scroll cells in VDP2 VRAM. A game asks for a tile by
 * key (a u32 it chooses: a CPS tile number, with the palette kept out of the key) and gets a slot number, uploading the pixels only on a miss.
 *
 *   - lookup by hash chain (one 8 byte record per slot: key, stamp, next, so a probe touches one cache line a node);
 *   - eviction by clock hand over slots not stamped this frame, so no tile the current picture uses is ever replaced;
 *   - optional protection of the previous picture's slots (VDP1 is still plotting them when the next build starts);
 *   - a two entry memo of the last answer per column parity (runs of one tile, mostly blank, skip the lookup);
 *   - a negative cache for keys that are blank or not in the pack, so a transparent tile costs one probe per frame, not a pack search.
 * Capacity refusals (every slot in use this frame) are counted, never silent.
 *
 * What a game supplies: the memory (slot records, hash heads, optional negative cache) and three hooks:
 *   fetch(ctx, key, &payload)   SAT_TC_PAYLOAD with *payload set, SAT_TC_BLANK (no visible pixel: nothing to draw), or SAT_TC_MISSING (key not in the pack)
 *   upload(dst, src, bytes)     copy the payload into the slot's VRAM (the game chooses its fastest copy: long writes, DMA)
 * Sizes are parameters (slot bytes, capacity, reserved slots). Nothing here knows a tile format. Keys must be below 2^31 when the negative cache is used. */
#ifndef SAT_TILECACHE_H
#define SAT_TILECACHE_H
#include <stdint.h>

#define SAT_TC_NOSLOT 0xffffu
#define SAT_TC_NOKEY 0xffffffffu
#define SAT_TC_PAYLOAD 1
#define SAT_TC_BLANK 0
#define SAT_TC_MISSING (-1)

typedef struct SatTcSlot { uint32_t key; uint16_t stamp, next; } SatTcSlot;

typedef struct SatTileCache {
    uint8_t *vram;            /* first slot */
    uint32_t slot_bytes;
    uint16_t capacity;        /* slots */
    uint16_t first;           /* slots below this are reserved for the game's own use */
    uint16_t hand;
    uint16_t used;            /* distinct slots stamped this frame */
    uint16_t stamp, prev_stamp; /* current frame, and the last plot that was really submitted (0 none) */
    int protect_prev;         /* nonzero: slots of prev_stamp are not evicted (VDP1 may still be reading them) */
    SatTcSlot *slots;
    uint16_t *head;
    uint16_t hmask;           /* hash heads - 1, a power of two minus one */
    uint32_t *neg;            /* negative cache, entries of tag = key << 1 | missing; NULL for none */
    uint32_t neg_mask;        /* entries - 1 */
    uint32_t memo_key[2];
    uint16_t memo_slot[2];
    int (*fetch)(void *ctx, uint32_t key, const uint8_t **payload);
    void (*upload)(uint8_t *dst, const uint8_t *src, uint32_t bytes);
    void *ctx;
    uint32_t uploads;         /* this frame */
    uint32_t missing;         /* keys the pack lacked, cumulative */
    uint32_t refused;         /* capacity refusals, cumulative */
} SatTileCache;

void sat_tc_init(SatTileCache *c, uint8_t *vram, uint32_t slot_bytes, uint16_t capacity, uint16_t first,
                 SatTcSlot *slots, uint16_t *head, uint32_t head_count, uint32_t *neg, uint32_t neg_count,
                 int (*fetch)(void *, uint32_t, const uint8_t **), void (*upload)(uint8_t *, const uint8_t *, uint32_t), void *ctx);
/* Start of a picture's build: new stamp, memos cleared, per-frame counters reset. */
void sat_tc_frame(SatTileCache *c);
/* Slot number for key, uploading on a miss. SAT_TC_NOSLOT for blank, missing or refused. */
uint16_t sat_tc_get(SatTileCache *c, uint32_t key);
/* VRAM address of a slot. */
static inline uint8_t *sat_tc_slot_addr(const SatTileCache *c, uint16_t slot) { return c->vram + (uint32_t)slot * c->slot_bytes; }
/* The plot of this build was submitted: its slots are now the previous plot's. */
void sat_tc_commit(SatTileCache *c);
/* The build was abandoned after touching slots: give every slot stamped now back the protection of the last submitted plot. */
void sat_tc_abandon(SatTileCache *c);
/* Forget what the negative cache learned (a new pack came in: a tile once missing may exist now). */
void sat_tc_forget_negative(SatTileCache *c);
#endif
