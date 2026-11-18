/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn release/v0.1.2-beta, saturn/rt/boot.c (cart_soak), made a pure function so it also runs on a PC.
 *
 * The cart timing soak test. Two words written and read back once passed on a cart too marginal for the faster A-bus timing (a Fenrir, v0.1.2-beta field
 * report: speckled menus and garbled sprites on the console, nothing wrong in an emulator). The test fills four blocks, one per bit pattern, writes them
 * through the cache-through alias and reads them back through the cached alias, the way the game reads the cart: line fills of lines never fetched before.
 * A word that comes back wrong sets bits in the result. The caller purges the cache afterwards (sat_boot_cart_soak does). */
#ifndef SAT_CART_SOAK_H
#define SAT_CART_SOAK_H
#include "../include/sat_hw.h"

#define SAT_SOAK_PATTERNS 4   /* x = 0, 0x55555555, 0xaaaaaaaa, 0xffffffff, each xor'ed into word i * 0x9e3779b9 */

/* Fills `blocks` blocks of `words` words at `w` (the write side) and checks them through `r` (the read side; the same memory seen through the cache on a
   console). Returns the OR of every wrong bit, 0 when all words came back right. *done is the number of blocks run: `blocks`, at most
   SAT_SOAK_PATTERNS. Pure: no hardware access, so tests/c/t_soak.c runs it on a PC. */
uint32_t sat_soak_run(volatile uint32_t *w, const volatile uint32_t *r, unsigned blocks, unsigned words, unsigned *done);

/* The test on the cart at SAT_CART_SOAK_BASE with the current A-bus timing, then a cache purge. Nonzero: some word came back wrong.
   sat_boot_soak_bad and sat_boot_soak_blocks keep the last result for test runs (the wrong bits; the blocks that ran, SAT_SOAK_PATTERNS when all did). */
extern volatile uint32_t sat_boot_soak_bad;
extern volatile uint32_t sat_boot_soak_blocks;
int sat_boot_cart_soak(void);
#endif
