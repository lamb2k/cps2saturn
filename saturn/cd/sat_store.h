/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/rt/boot.c (the SECTOR_STORE block: vread, load_regions).
 *
 * Round files read from a shared sector store, and the "regions" format a round file carries (the cart pages a stage restores).
 * Pure C: all disc access goes through four callbacks, so the same code runs on a console (saturn/cd/sat_gfs_io.c binds them to SGL's GFS)
 * and in the host tests, where the callbacks read an in-memory STORE.BIN built by tools/sector_store.py.
 *
 * STORE.BIN (tools/sector_store.py, big endian, 2048 byte sectors):
 *   sector 0     u32 'SST1', u32 rounds, then per round u32 first run, u32 run count
 *   sectors 1..  runs: u32 each, (store sector << 14) | sectors. A round's runs read in order are the round file, byte for byte.
 * Round file (what the runs spell):
 *   sector 0     u32 count, then count pairs of u32 (destination, bytes). bytes is a multiple of 2048. Destination 1 is the MARK: no data;
 *                the callback runs, so the caller can take what was loaded so far before later regions overwrite it.
 *   then         the regions' bytes in order, each read to its destination.
 * Region bytes with bit 0 set mean "the game's special region" (for example a compressed tile region, see sat_lzdec.h): the special hook
 * reads it; the byte count without bit 0 is its size in the stream.
 *
 * What a game supplies: the four IO callbacks (or sat_gfs_io.c), the 2048 byte head buffer, optionally the mark and special hooks. */
#ifndef SAT_STORE_H
#define SAT_STORE_H
#include <stdint.h>

#define SAT_SECTOR 2048u
#define SAT_STORE_MAGIC 0x53535431u   /* 'SST1' */
#define SAT_REGION_MARK 1u
#define SAT_REGION_MAX 255u           /* pairs that fit in the head sector after the count word */

typedef struct SatSectorIO {
    int (*seek)(void *h, int32_t sector);                    /* absolute sector in the store file; 0 ok */
    int (*read)(void *h, int32_t sectors, void *dest);       /* sectors from the current position, advancing it; 0 ok */
    void (*tick)(void *h);                                   /* progress (boot display), may be NULL */
    void *h;
} SatSectorIO;

typedef struct SatStore {
    SatSectorIO io;
    uint32_t dir[512];        /* sector 0 of the store, kept so a load seeks only to its own runs */
    uint32_t runs[512];       /* the run table sector last read */
    int32_t run_sec;          /* its store sector number, -1 none */
    int32_t run_next, run_end;/* next run index, one past the round's last */
    int32_t run_at, run_left; /* position inside the current run, sectors left in it */
    int reseek;               /* another reader moved the file position: seek to run_at before the next read */
    int ready;
} SatStore;

typedef struct SatRegionHooks {
    void (*mark)(void *user);
    /* Maps a destination word of the head sector to a pointer. NULL means the word is the address (the Saturn). Host tests map it into a buffer. */
    uint8_t *(*addr)(uint32_t dest, void *user);
    /* Called for a region with bit 0 set in its byte count. head is the head sector, i the region index.
       Return 0 = handled (counts sectors via *sectors_read), nonzero = failure (returned as the load's error). */
    int (*special)(SatStore *s, const uint32_t *head, uint32_t i, int32_t *sectors_read, void *user);
    void *user;
} SatRegionHooks;

/* Reads the directory once (sector 0). 0 ok, -0x100 bad magic or read error. */
int sat_store_open(SatStore *s, const SatSectorIO *io);
/* Select a round: 0 ok, -0x100 round out of range. The head sector is then read with sat_store_read. */
int sat_store_select(SatStore *s, uint32_t round);
/* Read `secs` sectors of the selected round's stream into dest, following its runs. 0 ok, negative code on failure. */
int sat_store_read(SatStore *s, int32_t secs, uint8_t *dest);
/* Load a round: the head sector into head (2048 bytes; words in the CPU's order, which on the big endian SH-2 is the disc's), then each region to its destination.
   Returns sectors read (head included), or a negative code: -0x100/-0x101 store or head, -4 - i region i failed. */
long sat_store_load_round(SatStore *s, uint32_t round, uint32_t *head, const SatRegionHooks *hooks);
/* Total rounds in the store. */
uint32_t sat_store_rounds(const SatStore *s);

/* Names: round number to a root file name "R000.BIN". buf at least 9 bytes. */
void sat_store_round_name(char *buf, uint32_t round);
#endif
