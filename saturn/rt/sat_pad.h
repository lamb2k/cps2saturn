/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/rt/pad.c (sat_pad_tick, the INTBACK sequence) and saturn/rt/boot.c (cd_pad).
 *
 * Saturn pad through the SMPC, never blocking: one INTBACK is issued at each vblank and its result is taken at the next.
 * Command order matters: write the input registers, set SF, THEN write the command. The SMPC clears SF when the command ends, and an SF set
 * after the command could land after a fast command had finished and leave SF stuck. A "more data queued" status (SR bit 5) is dropped with a
 * break request (IREG0 = 0x40) before the next command, or the SMPC ignores every other command until it is.
 *
 * Pad word, active low (a pressed button is 0):
 *   15 Right, 14 Left, 13 Down, 12 Up, 11 Start, 10 A, 9 C, 8 B, 7 R, 6 X, 5 Y, 4 Z, 3 L.
 * Port 2 is read only when a plain pad is in it (a multitap or another device reads as idle).
 *
 * What a game supplies: a SatPadMap table that turns Saturn bits into its own input latch bits, and a call to sat_pad_tick() first thing in each vblank. */
#ifndef SAT_PAD_H
#define SAT_PAD_H
#include <stdint.h>

#define SAT_PAD_RIGHT 0x8000u
#define SAT_PAD_LEFT 0x4000u
#define SAT_PAD_DOWN 0x2000u
#define SAT_PAD_UP 0x1000u
#define SAT_PAD_START 0x0800u
#define SAT_PAD_A 0x0400u
#define SAT_PAD_C 0x0200u
#define SAT_PAD_B 0x0100u
#define SAT_PAD_R 0x0080u
#define SAT_PAD_X 0x0040u
#define SAT_PAD_Y 0x0020u
#define SAT_PAD_Z 0x0010u
#define SAT_PAD_L 0x0008u

/* Register access, so the sequence can be checked on a PC. off is the byte offset from 0x20100000. */
typedef struct SatSmpcOps {
    uint8_t (*rd)(void *ctx, unsigned off);
    void (*wr)(void *ctx, unsigned off, uint8_t v);
    void *ctx;
} SatSmpcOps;

extern uint32_t sat_pad_raw, sat_pad_raw2;   /* last good pad words, active low; 0xffff when nothing is plugged in */

void sat_pad_tick(void);                                   /* hardware registers */
void sat_pad_tick_ops(const SatSmpcOps *ops);              /* the same sequence through ops */

typedef struct SatPadMap { uint16_t saturn_mask; uint16_t game_mask; } SatPadMap;
/* Game latch from a pad word: starts from idle_value (the game's "nothing pressed", all ones for an active-low latch),
   clears each game_mask whose saturn_mask is pressed. active_low_out: 1 clears bits, 0 sets them. */
uint32_t sat_pad_map(uint32_t raw, const SatPadMap *map, unsigned n, uint32_t idle_value, int active_low_out);
#endif
