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
    uint16_t hold_span;       /* decode ahead with a hold (lane spikes): a slot whose stamp is 1 to hold_span frames in the future is not evicted; 0 (the default) turns the rule off */
    uint32_t held_hits;       /* -DSAT_TC_HOLDSTAT builds only: first touches of a picture that found a held slot, cumulative */
} SatTileCache;

void sat_tc_init(SatTileCache *c, uint8_t *vram, uint32_t slot_bytes, uint16_t capacity, uint16_t first,
                 SatTcSlot *slots, uint16_t *head, uint32_t head_count, uint32_t *neg, uint32_t neg_count,
                 int (*fetch)(void *, uint32_t, const uint8_t **), void (*upload)(uint8_t *, const uint8_t *, uint32_t), void *ctx);
/* Start of a picture's build: new stamp, memos cleared, per-frame counters reset. */
void sat_tc_frame(SatTileCache *c);
/* Slot number for key, uploading on a miss. SAT_TC_NOSLOT for blank, missing or refused. */
uint16_t sat_tc_get(SatTileCache *c, uint32_t key);
/* Same result and same effects as sat_tc_get, with the hit that sat_tc_get takes most often (the memo, or the first slot of the hash chain) done in the caller without a call (lane slavecost: a picture asks for 300 to
   400 tiles, nearly all are in the cache, and the call with its register saves was a third of a hit). Anything else goes to sat_tc_get. -DSAT_TC_NOFAST makes it a plain call. */
#ifndef SAT_TC_NOFAST
static inline uint16_t sat_tc_get_fast(SatTileCache *c, uint32_t key)
{
    uint32_t way = key & 1;
    if (c->memo_key[way] == key) return c->memo_slot[way];
    {
        uint16_t s = c->head[(key ^ (key >> 10)) & c->hmask];
        if (s != SAT_TC_NOSLOT) {
            SatTcSlot *r = &c->slots[s];
            if (r->key == key) {
                if (r->stamp != c->stamp) {
#ifdef SAT_TC_HOLDSTAT
                    if ((uint16_t)((uint16_t)(r->stamp - c->stamp) - 1u) < c->hold_span) c->held_hits++;
#endif
                    r->stamp = c->stamp; c->used++;
                }
                c->memo_key[way] = key; c->memo_slot[way] = s;
                return s;
            }
        }
    }
    return sat_tc_get(c, key);
}
#else
#define sat_tc_get_fast sat_tc_get
#endif
/* Decode ahead (lane cadence): the same lookup as sat_tc_get, called between two builds, for a tile a coming picture will probably need. A miss decodes and uploads it into a slot
   that neither the build just submitted nor the picture before it uses, and stamps it as the submitted build's, so the next build's sweep leaves it alone. No memo is touched.
   Call it only after sat_tc_commit of a build that was plotted, before the next sat_tc_frame. SAT_TC_NOSLOT for blank, missing or refused. */
uint16_t sat_tc_prefetch(SatTileCache *c, uint32_t key);
/* Decode ahead for a tile that is needed `hold` pictures from now or sooner (lane spikes, 1 <= hold <= hold_span; the caller sets c->hold_span once). The same lookup as sat_tc_prefetch, but the slot (found or
   new) is stamped `hold` frames in the future instead of the current frame: the clock sweep skips a slot stamped 1 to hold_span frames ahead, so a tile decoded for a pose that starts a few pictures
   from now survives the builds in between; the first picture that uses it restamps it as any hit does (the hold ends), and when its time has passed it ages like any other slot. A slot that the last submitted
   plot or this build already stamped (the stamp is the current one) keeps its stamp, and a slot held longer keeps its hold. Same call rules as sat_tc_prefetch. SAT_TC_NOSLOT for blank, missing or refused. */
uint16_t sat_tc_prefetch_hold(SatTileCache *c, uint32_t key, uint16_t hold);
/* VRAM address of a slot. */
static inline uint8_t *sat_tc_slot_addr(const SatTileCache *c, uint16_t slot) { return c->vram + (uint32_t)slot * c->slot_bytes; }
/* The plot of this build was submitted: its slots are now the previous plot's. */
void sat_tc_commit(SatTileCache *c);
/* The build was abandoned after touching slots: give every slot stamped now back the protection of the last submitted plot. */
void sat_tc_abandon(SatTileCache *c);
/* Forget what the negative cache learned (a new pack came in: a tile once missing may exist now). */
void sat_tc_forget_negative(SatTileCache *c);
#endif
