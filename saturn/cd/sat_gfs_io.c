/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/rt/boot.c (load, load_regions) and loader/loader.c. See sat_gfs_io.h. */
#include "SEGA_GFS.H"
#include "sat_gfs_io.h"
#include "../boot/sat_diag.h"

static unsigned char gfs_work[GFS_WORK_SIZE(1)];
static GfsDirTbl gfs_dir;
static GfsDirName gfs_names[SAT_BOOT_NAMES];

static SatStore store;
static uint32_t head[SAT_SECTOR / 4];
static GfsHn store_handle;

int sat_gfs_init(void)
{
    GFS_DIRTBL_TYPE(&gfs_dir) = GFS_DIR_NAME;
    GFS_DIRTBL_DIRNAME(&gfs_dir) = gfs_names;
    GFS_DIRTBL_NDIR(&gfs_dir) = SAT_BOOT_NAMES;
    return (int)GFS_Init(1, gfs_work, &gfs_dir);
}

long sat_gfs_load_file(const char *name, void *dest, unsigned code)
{
    Sint32 id = GFS_NameToId((Sint8 *)name), ss, n, last, got, total = 0, left;
    unsigned char *d = (unsigned char *)dest;
    GfsHn h;
    volatile unsigned long *diag = (volatile unsigned long *)SAT_LOADER_DIAG_ADDR;
    if (id < 0) sat_diag_fail(code | 1, SAT_C_RED, (unsigned)id);
    h = GFS_Open(id);
    if (!h) sat_diag_fail(code | 2, SAT_C_RED, 0);
    GFS_GetFileSize(h, &ss, &n, &last);
    GFS_SetTmode(h, GFS_TMODE_CPU);
    for (left = n; left > 0; ) {
        Sint32 c = left > SAT_BOOT_CHUNK ? SAT_BOOT_CHUNK : left;
        got = GFS_Fread(h, c, d, ss * c);
        if (got <= 0) { GFS_Close(h); sat_diag_fail(code | 3, SAT_C_RED, (unsigned)got); }
        total += got; d += ss * c; left -= c;
        sat_diag_tick();
    }
    GFS_Close(h);
    diag[3] = code; diag[4] = (unsigned long)total;
    return total;
}

static int io_seek(void *h, int32_t sector) { return GFS_Seek((GfsHn)h, (Sint32)sector, GFS_SEEK_SET) < 0; }
static int io_read(void *h, int32_t sectors, void *dest) { return GFS_Fread((GfsHn)h, (Sint32)sectors, dest, sectors * 2048) != sectors * 2048; }
static void io_tick(void *h) { (void)h; sat_diag_tick(); }

long sat_gfs_load_regions(const char *name, void (*mark)(void))
{
    uint32_t round = (uint32_t)((name[1] - '0') * 100 + (name[2] - '0') * 10 + (name[3] - '0'));
    Sint32 id;
    SatSectorIO io;
    SatRegionHooks hooks = { 0, 0, 0, 0 };
    long r;
    if (GFS_Init(1, gfs_work, &gfs_dir) < 0) return -1;
    id = GFS_NameToId((Sint8 *)"STORE.BIN");
    if (id < 0) { GFS_Reset(); return -2; }
    store_handle = GFS_Open(id);
    if (!store_handle) { GFS_Reset(); return -3; }
    GFS_SetTmode(store_handle, GFS_TMODE_CPU);
    io.seek = io_seek; io.read = io_read; io.tick = io_tick; io.h = (void *)store_handle;
    /* The directory is read once and kept, so a later load seeks only to its own runs (the loader stays resident). */
    if (!store.ready || store.io.h != io.h) {
        if (sat_store_open(&store, &io)) { GFS_Close(store_handle); GFS_Reset(); return -0x100; }
    } else store.io = io;
    hooks.mark = (void (*)(void *))mark;
    r = sat_store_load_round(&store, round, head, &hooks);
    GFS_Close(store_handle);
    GFS_Reset();
    return r;
}
