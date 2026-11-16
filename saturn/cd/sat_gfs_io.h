/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/rt/boot.c (load, load_regions) and loader/loader.c (the GFS bring-up).
 *
 * Binds the loader to Sega's GFS (the CD file system of the Saturn SDK / SGL). Needs SEGA_GFS.H and the SGL libraries from your own SDK copy,
 * which are not part of this kit. Every other saturn/ module is free of them.
 *
 * What a game supplies: nothing but the file names. The root directory table size is SAT_BOOT_NAMES (sat_cfg.h). */
#ifndef SAT_GFS_IO_H
#define SAT_GFS_IO_H
#include "sat_store.h"

int sat_gfs_init(void);                                                 /* GFS_Init over the root directory: file count, or negative */
/* Read one root file to dest in SAT_BOOT_CHUNK sectors, ticking the boot display between chunks. Returns bytes read.
   A failure stops on the boot display with code | 1 (not found), | 2 (cannot open), | 3 (read failed) and never returns. */
long sat_gfs_load_file(const char *name, void *dest, unsigned code);
/* The region loader the runtime calls between rounds (the loader publishes it at SAT_LOADER_API_ADDR[0]; the caller has masked interrupts and
   stopped the slave). name is "RNNN.BIN": the round number is read from its digits. Returns sectors read, or a negative stage. */
long sat_gfs_load_regions(const char *name, void (*mark)(void));
#endif
