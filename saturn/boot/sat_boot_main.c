/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/rt/boot.c (main). The file list is a table the game supplies instead of five fixed names.
 *
 * The loader's main(), table driven: boot display, clock change, 4 MB cart, GFS, then each listed file to its address, then the runtime.
 * What a game supplies:
 *   const SatBootFile sat_boot_files[]; const unsigned sat_boot_file_count;   the files to load, in disc order if the drive should sweep once
 *   optionally sat_boot_before_enter(): runs after the loads, before the runtime (a save-RAM read, a data patch). Weak: the default does nothing. */
#include "sat_boot.h"
#include "../cd/sat_gfs_io.h"
#include "sat_boot_main.h"

__attribute__((weak)) void sat_boot_before_enter(void) {}

void sat_boot_main(void)
{
    unsigned i;
    volatile unsigned long *api = (volatile unsigned long *)SAT_LOADER_API_ADDR;
    sat_diag_init(0x8000u);                 /* grey screen: the BIOS ran 0.BIN */
    sat_diag_install_exceptions();
    sat_diag_stage(0);                      /* band 1: the loader runs */
    sat_boot_clock_change();                /* first: it resets the chips (and in some emulators the cart RAM), so nothing is loaded yet */
    sat_diag_stage(0);                      /* the clock change is done */
    sat_boot_cart_enable();
    if (sat_gfs_init() < 0) sat_diag_fail(0xe001u, SAT_C_RED, 0);
    sat_diag_stage(0);                      /* GFS_Init passed */
    for (i = 0; i < sat_boot_file_count; i++) {
        sat_diag_stage(0);
        sat_gfs_load_file(sat_boot_files[i].name, sat_boot_files[i].dest, sat_boot_files[i].code);
    }
    sat_boot_before_enter();
    api[0] = (unsigned long)sat_gfs_load_regions;
    sat_diag_stage(0);                      /* the runtime is entered next */
    sat_boot_enter();
}
