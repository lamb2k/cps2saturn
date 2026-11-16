/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Written for the kit (the table form of the file list in avpsaturn v0.1.0-beta, saturn/rt/boot.c main). The table a game gives sat_boot_main.c. */
#ifndef SAT_BOOT_MAIN_H
#define SAT_BOOT_MAIN_H
typedef struct SatBootFile {
    const char *name;     /* root file name on the disc, upper case, e.g. "RT.BIN" */
    void *dest;           /* load address */
    unsigned code;        /* failure code base shown on the boot display (the low bits carry the step: 1 not found, 2 open, 3 read) */
} SatBootFile;
extern const SatBootFile sat_boot_files[];
extern const unsigned sat_boot_file_count;
void sat_boot_main(void);
void sat_boot_before_enter(void);
#endif
