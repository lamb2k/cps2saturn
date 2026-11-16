/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/rt/boot.c (vread, load_regions; SECTOR_STORE branch). See sat_store.h.
 * Left in AvP: the coalescing of tiny regions (SAT_LOAD_COALESCE, default off there) and the compressed tile region (a special hook). */
#include "sat_store.h"

/* The disc words are big endian. The SH-2 is too (nothing to do); a little endian host test swaps the sectors that are tables (directory, runs, head). */
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
static void words_to_host(uint32_t *w, unsigned n) { while (n--) { *w = __builtin_bswap32(*w); w++; } }
#else
static void words_to_host(uint32_t *w, unsigned n) { (void)w; (void)n; }
#endif

#define RUNS_PER_SECTOR 512
#define READ_CHUNK 128   /* sectors per device read, so the progress tick moves while a big region loads */

uint32_t sat_store_rounds(const SatStore *s) { return s->dir[1]; }

void sat_store_round_name(char *buf, uint32_t r)
{
    buf[0] = 'R'; buf[1] = (char)('0' + r / 100 % 10); buf[2] = (char)('0' + r / 10 % 10); buf[3] = (char)('0' + r % 10);
    buf[4] = '.'; buf[5] = 'B'; buf[6] = 'I'; buf[7] = 'N'; buf[8] = 0;
}

int sat_store_open(SatStore *s, const SatSectorIO *io)
{
    s->io = *io;
    s->run_sec = -1; s->run_next = s->run_end = 0; s->run_at = s->run_left = 0; s->reseek = 0; s->ready = 0;
    if (s->io.seek(s->io.h, 0) || s->io.read(s->io.h, 1, s->dir)) { s->dir[0] = 0; return -0x100; }
    words_to_host(s->dir, 512);
    if (s->dir[0] != SAT_STORE_MAGIC) { s->dir[0] = 0; return -0x100; }
    s->ready = 1;
    return 0;
}

int sat_store_select(SatStore *s, uint32_t round)
{
    if (!s->ready || round >= s->dir[1]) return -0x100;
    s->run_next = (int32_t)s->dir[2 + round * 2];
    s->run_end = s->run_next + (int32_t)s->dir[3 + round * 2];
    s->run_left = 0;
    return 0;
}

int sat_store_read(SatStore *s, int32_t secs, uint8_t *dest)
{
    while (secs) {
        int32_t take;
        if (!s->run_left) {
            int32_t sec;
            uint32_t w;
            if (s->run_next >= s->run_end) return -1;
            sec = 1 + s->run_next / RUNS_PER_SECTOR;
            if (sec != s->run_sec) {
                if (s->io.seek(s->io.h, sec) || s->io.read(s->io.h, 1, s->runs)) return -2;
                words_to_host(s->runs, 512);
                s->run_sec = sec;
            }
            w = s->runs[s->run_next % RUNS_PER_SECTOR];
            s->run_at = (int32_t)(w >> 14); s->run_left = (int32_t)(w & 0x3fffu); s->run_next++;
            if (s->io.seek(s->io.h, s->run_at)) return -3;
        } else if (s->reseek) {
            if (s->io.seek(s->io.h, s->run_at)) return -3;
        }
        s->reseek = 0;
        take = secs < s->run_left ? secs : s->run_left;
        if (take > READ_CHUNK) take = READ_CHUNK;
        if (s->io.read(s->io.h, take, dest)) return -4;
        if (s->io.tick) s->io.tick(s->io.h);
        s->run_at += take; s->run_left -= take; secs -= take; dest += (uint32_t)take * SAT_SECTOR;
    }
    return 0;
}

long sat_store_load_round(SatStore *s, uint32_t round, uint32_t *head, const SatRegionHooks *hooks)
{
    long total = 1;
    uint32_t i, n;
    int r = sat_store_select(s, round);
    if (r) return r;
    if (sat_store_read(s, 1, (uint8_t *)head)) return -0x101;
    words_to_host(head, 512);
    n = head[0];
    if (n > SAT_REGION_MAX) return -0x101;
    for (i = 0; i < n; i++) {
        uint32_t dest = head[1 + i * 2], bytes = head[2 + i * 2];
        int32_t secs = (int32_t)(bytes / SAT_SECTOR);
        if (dest == SAT_REGION_MARK) { if (hooks && hooks->mark) hooks->mark(hooks->user); continue; }
        if (bytes & 1u) {
            int32_t got = 0;
            if (!hooks || !hooks->special || hooks->special(s, head, i, &got, hooks->user)) return -4 - (long)i;
            total += got;
            continue;
        }
        if (sat_store_read(s, secs, hooks && hooks->addr ? hooks->addr(dest, hooks->user) : (uint8_t *)(uintptr_t)dest)) return -4 - (long)i;
        total += secs;
    }
    return total;
}
