/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/gfx/sat_gfx.c (cache_setup, cache_find, cache_get, cache_frame, plot_abandon_build). The pack format,
 * the sprite-pair experiments, slot hints and the diagnostics stayed in AvP. See sat_tilecache.h. */
#include "sat_tilecache.h"

#define HASH(c, k) (((k) ^ ((k) >> 10)) & (c)->hmask)

void sat_tc_forget_negative(SatTileCache *c)
{
    uint32_t i;
    if (c->neg) for (i = 0; i <= c->neg_mask; i++) c->neg[i] = SAT_TC_NOKEY;
}

void sat_tc_init(SatTileCache *c, uint8_t *vram, uint32_t slot_bytes, uint16_t capacity, uint16_t first,
                 SatTcSlot *slots, uint16_t *head, uint32_t head_count, uint32_t *neg, uint32_t neg_count,
                 int (*fetch)(void *, uint32_t, const uint8_t **), void (*upload)(uint8_t *, const uint8_t *, uint32_t), void *ctx)
{
    uint32_t i;
    c->vram = vram; c->slot_bytes = slot_bytes; c->capacity = capacity; c->first = first; c->hand = first; c->used = 0;
    c->stamp = 0; c->prev_stamp = 0; c->protect_prev = 0;
    c->slots = slots; c->head = head; c->hmask = (uint16_t)(head_count - 1);
    c->neg = neg; c->neg_mask = neg_count ? neg_count - 1 : 0;
    c->fetch = fetch; c->upload = upload; c->ctx = ctx;
    c->uploads = 0; c->missing = 0; c->refused = 0;
    for (i = 0; i < capacity; i++) { slots[i].key = SAT_TC_NOKEY; slots[i].stamp = 0; slots[i].next = SAT_TC_NOSLOT; }
    for (i = 0; i < head_count; i++) head[i] = SAT_TC_NOSLOT;
    c->memo_key[0] = c->memo_key[1] = SAT_TC_NOKEY;
    c->memo_slot[0] = c->memo_slot[1] = SAT_TC_NOSLOT;
    sat_tc_forget_negative(c);
}

void sat_tc_frame(SatTileCache *c)
{
    c->stamp = (uint16_t)(c->stamp + 1u == 0x10000u ? 1u : c->stamp + 1u);   /* never 0: 0 means "never used" */
    c->used = 0;
    c->uploads = 0;
    c->memo_key[0] = c->memo_key[1] = SAT_TC_NOKEY;
}

void sat_tc_commit(SatTileCache *c) { c->prev_stamp = c->stamp; }

void sat_tc_abandon(SatTileCache *c)
{
    uint16_t i;
    /* A hit restamps even a slot used by the previous plot. If the submission failed, put the previous plot's protection back on every slot
       this build touched, including new uploads. Runs only on failure, needs no list. */
    for (i = 0; i < c->capacity; i++)
        if (c->slots[i].stamp == c->stamp) c->slots[i].stamp = c->prev_stamp;
}

static uint16_t tc_find(SatTileCache *c, uint32_t key)
{
    uint32_t h = HASH(c, key), way = 0, tag = 0;
    uint16_t s = c->head[h], n = SAT_TC_NOSLOT;
    uint32_t scan;
    const uint8_t *payload = 0;
    int kind;
    while (s != SAT_TC_NOSLOT) {
        SatTcSlot *r = &c->slots[s];
        if (r->key == key) {
            if (r->stamp != c->stamp) { r->stamp = c->stamp; c->used++; }
            return s;
        }
        s = r->next;
    }
    if (c->neg) {
        tag = key << 1;
        way = (tag ^ (tag >> 11)) & c->neg_mask;
        if ((c->neg[way] & ~1u) == tag) return SAT_TC_NOSLOT;   /* known blank or known missing */
    }
    kind = c->fetch(c->ctx, key, &payload);
    if (kind != SAT_TC_PAYLOAD) {
        if (kind == SAT_TC_MISSING) c->missing++;
        if (c->neg) c->neg[way] = tag | (kind == SAT_TC_MISSING ? 1u : 0u);
        return SAT_TC_NOSLOT;
    }
    for (scan = c->first; scan < c->capacity; scan++) {
        uint16_t t = c->hand;
        c->hand = (uint16_t)(t + 1u >= c->capacity ? c->first : t + 1u);
        if (c->slots[t].stamp != c->stamp && !(c->protect_prev && c->prev_stamp && c->slots[t].stamp == c->prev_stamp)) { n = t; break; }
    }
    if (n == SAT_TC_NOSLOT) { c->refused++; return SAT_TC_NOSLOT; }
    if (c->slots[n].key != SAT_TC_NOKEY) {
        uint16_t *link = &c->head[HASH(c, c->slots[n].key)];
        while (*link != n) link = &c->slots[*link].next;
        *link = c->slots[n].next;
    }
    c->slots[n].key = key; c->slots[n].stamp = c->stamp; c->used++;
    c->slots[n].next = c->head[h]; c->head[h] = n;
    c->upload(sat_tc_slot_addr(c, n), payload, c->slot_bytes);
    c->uploads++;
    return n;
}

uint16_t sat_tc_get(SatTileCache *c, uint32_t key)
{
    uint32_t way = key & 1;
    if (c->memo_key[way] != key) {
        c->memo_key[way] = key;
        c->memo_slot[way] = tc_find(c, key);
    }
    return c->memo_slot[way];
}

uint16_t sat_tc_prefetch(SatTileCache *c, uint32_t key)
{
    /* Between builds c->stamp is the stamp of the last submitted plot (sat_tc_commit made it prev_stamp), so tc_find neither evicts its slots nor the ones it just stamped; a hit restamps. */
    return tc_find(c, key);
}
