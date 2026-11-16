/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/gfx/sat_vdp2_cfg.h (the access cycle tables and the checks in its comments).
 *
 * VDP2 VRAM access cycle patterns that pass tools/vdp2_cycle_check.py (Sega's VDP2 manual, chapter 3) and ran on a console.
 * The VDP2 draws a scroll layer only if the cycle pattern gives it enough reads, in the right banks, at legal timings. Emulators are lenient about
 * a wrong pattern; a console shows garbage or nothing. Pick the pattern for your layer set and keep each register's value in one place: this header.
 *
 * Eight words, CYCA0L CYCA0U CYCA1L CYCA1U CYCB0L CYCB0U CYCB1L CYCB1U (registers 0x10 to 0x1e). Each word holds four timings, one nibble each; the
 * lower word is T0..T3, the upper T4..T7. Codes: 0..3 pattern names of NBG0..3, 4..7 cells of NBG0..3, e CPU, f no access.
 *
 * SAT_V2_CYC_HALF: NBG0 and NBG1 reduced to half width (ZMCTL bit 0 and 8), 16 colours, 2 x 2 cell characters, two word names; NBG2 and NBG3 1 x 1, 16 colours.
 *   Names: NBG0 twice, NBG1 twice, NBG2, NBG3. Cells: NBG0 twice, NBG1 twice, NBG2, NBG3. Needs RAMCTL 0x1300 (both banks split in two, CRAM mode 1).
 *     A0  2 3 1 1 | 6 7 f e    NBG2 names T0, NBG3 names T1, NBG1 names T2 T3, NBG2 cells T4, NBG3 cells T5, CPU T7 (no access at T6)
 *     A1  0 0 4 f | f 4 f e    NBG0 names T0 T1, NBG0 cells T2 T5, CPU T7
 *     B0, B1  5 5 f f | e e e e   NBG1 cells T0 T1, CPU T4 to T7 after no access at T3
 * SAT_V2_CYC_FLAT: no reduction, one name read and one cell read for each layer.
 *     A0  2 3 1 f | 6 7 f e    A1  0 f 4 f | f f f e    B0, B1  5 f f f | e e e e
 * Both are the owner's AvP values. A game with another layer set writes its own words and runs the checker on them (spec example:
 * saturn/gfx/vdp2_layout.example.json, which the host tests run on both patterns here).
 *
 * The CPU slots are what lets the runtime write VRAM; moving them breaks uploads, so keep the A0/A1 pair rule (the same slot in both banks with a
 * no-access slot in front) and the four-slot B run. */
#ifndef SAT_VDP2_CYCLES_H
#define SAT_VDP2_CYCLES_H
#define SAT_V2_RAMCTL_SPLIT 0x1300u   /* VRAM-A and VRAM-B each split in two banks, CRAM mode 1, no rotation data banks */
#define SAT_V2_CYC_HALF { 0x2311u, 0x67feu, 0x004fu, 0xf4feu, 0x55ffu, 0xeeeeu, 0x55ffu, 0xeeeeu }
#define SAT_V2_CYC_FLAT { 0x231fu, 0x67feu, 0x0f4fu, 0xfffeu, 0x5fffu, 0xeeeeu, 0x5fffu, 0xeeeeu }
#endif
