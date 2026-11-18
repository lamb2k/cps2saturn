/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn release/v0.1.2-beta, saturn/rt/boot.c (cart_soak). See sat_cart_soak.h. */
#include <stddef.h>
#include "sat_cart_soak.h"
#include "../include/sat_cfg.h"

volatile uint32_t sat_boot_soak_bad;
volatile uint32_t sat_boot_soak_blocks;

uint32_t sat_soak_run(volatile uint32_t *w, const volatile uint32_t *r, unsigned blocks, unsigned words, unsigned *done)
{
    uint32_t bad = 0, x = 0;
    unsigned b, i;
    for (b = 0; b < blocks && b < SAT_SOAK_PATTERNS; b++) {
        for (i = 0; i < words; i++) w[(size_t)b * words + i] = (i * 0x9e3779b9u) ^ x;
        for (i = 0; i < words; i++) bad |= r[(size_t)b * words + i] ^ ((i * 0x9e3779b9u) ^ x);
        x += 0x55555555u;
    }
    *done = b;
    return bad;
}

#ifndef SAT_HOST
int sat_boot_cart_soak(void)
{
    unsigned done = 0;
    uint32_t bad = sat_soak_run((volatile uint32_t *)SAT_UNC(SAT_CART_SOAK_BASE), (const volatile uint32_t *)SAT_CART_SOAK_BASE, SAT_SOAK_PATTERNS, SAT_CART_SOAK_WORDS, &done);
    SAT_CCR |= 0x10u;   /* CCR.CP: purge, so no line of this test outlives it */
    sat_boot_soak_bad = bad; sat_boot_soak_blocks = done;
    return bad != 0;
}
#endif
