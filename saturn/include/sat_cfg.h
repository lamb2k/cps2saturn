/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Written for the kit. The defaults are the values avpsaturn v0.1.0-beta ran on a console (saturn/rt/boot.c, saturn/rt/kernel.c, saturn/gfx/sat_gfx.c).
 *
 * How a game configures the saturn/ modules. Every address and size a module needs is a macro with a default here.
 * The game provides its own header and names it on the compiler line:   -DSAT_GAME_CFG='"mygame_cfg.h"'
 * That header is included first, so it can define any macro below. A module that needs a value the game must choose
 * (no sensible default) tests it with #error, so a missing value is a build failure and never a silent guess. */
#ifndef SAT_CFG_H
#define SAT_CFG_H
#ifdef SAT_GAME_CFG
#include SAT_GAME_CFG
#endif

/* ---- boot (saturn/boot) ---- */
#ifndef SAT_BOOT_ENTRY
#define SAT_BOOT_ENTRY 0x06014000u        /* where the loader hands over: the runtime's first instruction */
#endif
#ifndef SAT_LOADER_DIAG_ADDR
#define SAT_LOADER_DIAG_ADDR 0x06013fe0u   /* 8 words the loader leaves for a debugger: magic, last code, detail, ... */
#endif
#ifndef SAT_LOADER_API_ADDR
#define SAT_LOADER_API_ADDR 0x06013fd0u    /* words the runtime reads: [0] the region loader, [1..3] free for the game */
#endif
#ifndef SAT_DIAG_API_ADDR
#define SAT_DIAG_API_ADDR 0x06013fa0u      /* the boot display's call table (sat_diag.h), kept alive until the runtime's first picture */
#endif
#ifndef SAT_DIAG_TAB_ADDR
#define SAT_DIAG_TAB_ADDR 0x25e7fe00u      /* VDP2 VRAM: the back-screen colour table, one word per line; the game keeps these bytes clear */
#endif
#ifndef SAT_DIAG_LINES
#define SAT_DIAG_LINES 224
#endif
#ifndef SAT_BOOT_NAMES
#define SAT_BOOT_NAMES 64                  /* root directory entries the loader can see */
#endif
#ifndef SAT_BOOT_CHUNK
#define SAT_BOOT_CHUNK 128                 /* sectors per read, so the progress tick moves while a file loads */
#endif
#ifndef SAT_TVMD_ON
#define SAT_TVMD_ON 0x8101u                /* 352 x 224 NTSC, display on (SGL's value); 0x8000 is 320 x 224 */
#endif
#ifndef SAT_BOOT_CLOCK_28
#define SAT_BOOT_CLOCK_28 1                /* 1: 352/704 wide modes (28 MHz dot clock), 0: 320/640 (26 MHz); the BIOS runs 320. Keep SAT_TVMD_ON in step with it */
#endif
#ifndef SAT_CART_OURS_ASR0
#define SAT_CART_OURS_ASR0 0x23301ff0u     /* the A-bus timing tried after the BIOS's own timing has proved the cart */
#endif
#ifndef SAT_CART_OURS_AREF
#define SAT_CART_OURS_AREF 0x00000013u
#endif
#ifndef SAT_CART_SOAK_BASE
#define SAT_CART_SOAK_BASE 0x02700000u     /* cached address of the cart area the timing soak test overwrites: nothing may be loaded there yet (the cart is a 4 MB window at 0x02400000) */
#endif
#ifndef SAT_CART_SOAK_WORDS
#define SAT_CART_SOAK_WORDS 0x4000u        /* 32 bit words in each soak block (64 KB); four blocks, one per bit pattern, so 256 KB in all */
#endif
#ifndef SAT_CART_SAROO_ASR0
#define SAT_CART_SAROO_ASR0 0x38803880u    /* the A-bus timing a SAROO leaves after the BIOS clock change: it keeps its own timing, the loader must not rewrite it */
#endif

/* ---- hand-off (saturn/rt/sat_sync) ---- */
#ifndef SAT_SLAVE_STACK_WORDS
#define SAT_SLAVE_STACK_WORDS 256
#endif
#ifndef SAT_SLAVE_WAIT_MAX
#define SAT_SLAVE_WAIT_MAX 7000u           /* slave FRT ticks (phi/128): about two frames; a master with interrupts off cannot hold the slave */
#endif

/* ---- VDP1 (saturn/gfx/sat_vdp1) ---- */
#ifndef SAT_V1_TABLE_A
#define SAT_V1_TABLE_A 0x0000u             /* VDP1 VRAM offsets of the two command tables */
#endif
#ifndef SAT_V1_TABLE_B
#define SAT_V1_TABLE_B 0x8000u
#endif
#endif
