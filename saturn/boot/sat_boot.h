/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/rt/boot.c (clock_352, the cart bring-up in main()).
 *
 * First-stage loader steps that every Saturn port that uses the 4 MB RAM cart needs, in the order that works on a console:
 *   1. sat_boot_clock_change()  the BIOS runs the 320 dot clock. A 352 wide mode on it gives timing a TV cannot lock on (rolling noise).
 *                               The BIOS service does the SMPC command and resets the SCU and A-bus, so the cart comes AFTER it.
 *   2. sat_boot_cart_enable()   enable and verify the cart on the BIOS's own timing, then switch to a faster timing and verify again,
 *                               falling back to the BIOS timing if that fails. Stops with a coded failure on the boot display if no RAM answers.
 *   3. file loads (sat_gfs_io.h), then enter the runtime (sat_boot_enter()).
 * Failure codes shown on the stripes: 0xe0f0 cart did not answer, 0xe0f2 no 4 MB cart ID either, 0xe0f1 only the BIOS timing works and it
 * failed on the way back. A yellow band (stage colour) with 0x2001 means only the BIOS timing worked, not the faster one. */
#ifndef SAT_BOOT_H
#define SAT_BOOT_H
#include "sat_diag.h"

/* Returns nonzero if only the BIOS timing worked. Calls sat_diag_fail() if the cart does not answer at all. */
int sat_boot_cart_enable(void);
void sat_boot_clock_change(void);                  /* SAT_BOOT_CLOCK_28 selects the 352 wide clock; also rewrites VDP2 registers to zero as SGL does */
void sat_boot_spin(unsigned long n);
void sat_boot_enter(void) __attribute__((noreturn)); /* cache off and on (purge), then jump to SAT_BOOT_ENTRY */
void sat_boot_set_cache(int on);
#endif
