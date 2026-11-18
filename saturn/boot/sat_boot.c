/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/rt/boot.c (clock_352, ABUS_*, cart enable, the entry sequence at the end of main()). See sat_boot.h. */
#include "sat_boot.h"
#include "sat_cart_soak.h"

void sat_boot_spin(unsigned long n) { while (n--) __asm__ volatile ("nop"); }

/* The system clock change is the BIOS's own service (the function pointer at 0x06000320): 0 = 26 MHz, 320/640 modes, 1 = 28 MHz, 352/704 modes.
   SGL's slInitSystem calls it for a 352 mode. It also resets the SCU, A-bus (ASR0/ASR1 = 0x1ff01ff0, AREF = 0x1f), SCU timers and DMA to the BIOS defaults. */
void sat_boot_clock_change(void)
{
    unsigned o;
    SAT_BIOS_CHGSYSCK(SAT_BOOT_CLOCK_28 ? 1u : 0u);
    /* SGL's slInitSystem writes every VDP2 register (all zero but the ones it uses). A runtime that sets only what it uses relies on the rest
       being zero. The console's reset gives that only if it really resets them, so write the zeros (not TVMD or the read-only status registers). */
    SAT_VDP2_REG(0x02) = 0; SAT_VDP2_REG(0x06) = 0;
    for (o = 0x0e; o < 0x120; o += 2) SAT_VDP2_REG(o) = 0;
    sat_diag_set_tvmd(SAT_TVMD_ON);
    sat_diag_reinit();                  /* the chips were reset: the display again */
    sat_diag_info(0x4001u);             /* 4001: the BIOS clock change returned */
}

#define ABUS_BIOS() do { SAT_SCU32(SAT_SCU_ASR0) = 0x1ff01ff0u; SAT_SCU32(SAT_SCU_ASR1) = 0x1ff01ff0u; SAT_SCU32(SAT_SCU_AREF) = 0x0000001fu; } while (0)
#define ABUS_OURS() do { SAT_SCU32(SAT_SCU_ASR0) = SAT_CART_OURS_ASR0; SAT_SCU32(SAT_SCU_AREF) = SAT_CART_OURS_AREF; } while (0)

/* Cart bring-up. The clock change service has just reset the A-bus to the BIOS timing, so the cart comes after it.
   A SAROO (cartridge-slot ODE) runs its 4 MB RAM cart mode on its own timing, SAT_CART_SAROO_ASR0, which its hook on the clock change service sets. Writing the BIOS or
   the faster timing over it undid it, a likely cause of the SAROO boot reports. When the clock change left exactly that value it is kept: no BIOS timing, no faster
   timing, and the cart test still runs. Any other value (a console, a Fenrir, emulators) takes the path below.
   The faster timing has to pass the soak test (sat_boot_cart_soak: 256 KB, four bit patterns, read back through the cache as the game reads) or the cart goes back to
   the BIOS timing (yellow band, info 0x2001). A cart that keeps up keeps the faster timing; nothing needs a reset, it is one register write either way.
   Define SAT_CART_BIOS_TIMING to never try the faster timing. */
int sat_boot_cart_enable(void)
{
    volatile uint32_t *cart = (volatile uint32_t *)0x22700000u;   /* cache-through alias: a cached read could not tell a missing cart */
    unsigned id = 0;
    int tried = 0, k;
    int saroo = SAT_SCU32(SAT_SCU_ASR0) == SAT_CART_SAROO_ASR0;
    if (!saroo) ABUS_BIOS();   /* the clock change leaves the A-bus at these values; written again so nothing depends on how a console's SCU reset left them */
    *SAT_CART_ENABLE = 1;
    sat_boot_spin(300000);   /* a few ms for the cart after the reset */
    for (k = 0; k < 4; k++) {
        id = *SAT_CART_ID;
        cart[0] = 0x12345678u; cart[1] = 0xedcba987u;
        if (cart[0] == 0x12345678u && cart[1] == 0xedcba987u) break;
        sat_boot_spin(300000);
        *SAT_CART_ENABLE = 1;
    }
    sat_diag_info(0x1000u | id);   /* the cart's ID byte: 5c is a 4 MB RAM cart */
    if (cart[0] != 0x12345678u || cart[1] != 0xedcba987u) sat_diag_fail(id == 0x5c ? 0xe0f0u : 0xe0f2u, SAT_C_RED, id);
#ifndef SAT_CART_BIOS_TIMING
    if (!saroo) ABUS_OURS();
    *SAT_CART_ENABLE = 1;
    if (!saroo && sat_boot_cart_soak()) {
        ABUS_BIOS();
        *SAT_CART_ENABLE = 1;
        cart[0] = 0x12345678u; cart[1] = 0xedcba987u;
        if (cart[0] != 0x12345678u || cart[1] != 0xedcba987u) sat_diag_fail(0xe0f1u, SAT_C_RED, id);
        tried = 1;
    }
#endif
    sat_diag_stage(tried ? SAT_C_YELLOW : 0u);
    if (tried) sat_diag_info(0x2001u);
    return tried;
}

/* SH-2 cache control: bit 0 enable, bit 4 purge. */
void sat_boot_set_cache(int on)
{
    SAT_CCR = 0x10;                 /* purge, cache off */
    if (on) SAT_CCR = 0x01;
}
void sat_boot_enter(void)
{
    sat_boot_set_cache(1);
    ((void (*)(void))SAT_BOOT_ENTRY)();
    for (;;) ;
}
