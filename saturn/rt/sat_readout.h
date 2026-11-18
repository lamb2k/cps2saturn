/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn release/v0.1.2-beta, saturn/rt/fps_hud.c (the performance readout, lanes perf-reconcile, perf-hw and gamespeed, and the power-up
 * report of the hwboot lane), made game neutral: the numbers come in through a counter struct, the picture goes out through a cell callback.
 *
 * The console readout. A photograph of a TV is the only speed measurement a real Saturn gives (no emulator reproduces the console's timing), so a
 * first console disc carries a few short text lines, refreshed about once a second, that a person can read off a photo:
 *   PIC n    new pictures that reached the screen in the last second, normalised to 60 vblanks (VDP1 frame changes; 60 is the most)
 *   DONE n   game frames COMPLETED in the last second, per 60 vblanks (60 is full speed): vblanks minus the ones where the game had not finished its
 *            frame when the next vblank came. Not the same as the count of frame starts, which stays 60 while the work is cut off.
 *   MISS n   game frames that were not finished when the next vblank came; SKIP n vblanks where the slave was still drawing, so no new snapshot was
 *            taken; HELD n frame changes put off one vblank because VDP1 had not finished the plot
 *   <id> FLIP n VBL n   the build id (mode and source revision, a short string the game gives), the frame starts per 60 vblanks, the vblanks of the window
 *   TICK n   GAME SPEED: gameplay ticks the game ran per 60 vblanks. 60 is the arcade's rate and full speed; 45 means the game ran at 75 percent. It
 *            is the game's own clock, one byte the gameplay loop adds one to for every tick (SatReadoutCfg.tick_byte, your game's address, from
 *            your config). It reads 0 outside play (menus, fades, loads: the loop is held) and can read over 60 for a moment in scripted scenes.
 *            Call sat_ro_vblank() once a vblank so a byte that wraps at 256 never loses a tick, whatever the window length.
 *   PROF T g G g S g O g I g   the master's time over the window, percent of the field: T game tick, G graphics (the snapshot), S sound, O the rest of the
 *            work, I idle (the work was done and the master spun). Needs the game's own time counters (SatReadoutProf), any one unit.
 *   HW SND n OK|NO [TMO] [RB] TEST t   the power-up self-test line: SND = SCSP start attempts, OK = the SCSP RAM word read back and no SMPC wait ran
 *            out (NO otherwise), TMO = an SMPC wait ran out, RB = the master volume register read back (information); TEST bits 1 CRAM, 2 VDP2 VRAM,
 *            4 VDP1 VRAM read back as written (7 = all). Written for a first-boot report on a console: crushed colours and no sound on one power-up only.
 *
 * Nothing here touches hardware but sat_ro_chip_selftest(). The module formats text and tells a callback which cells changed; the game owns the font,
 * the layer and the rows (a game with no spare layer can draw the lines with VDP1 text instead). Default off in a release build. All numbers are
 * labelled HARDWARE when read off a console photo, and nothing else is a console result. */
#ifndef SAT_READOUT_H
#define SAT_READOUT_H
#include <stdint.h>

#define SAT_RO_COLS 24          /* characters a line may paint; longer text is cut */
enum { SAT_RO_ROW_PIC = 0, SAT_RO_ROW_MISS = 1, SAT_RO_ROW_ID = 2, SAT_RO_ROW_TICK = 3, SAT_RO_ROW_SELFTEST = 4, SAT_RO_ROW_PROF = 5, SAT_RO_ROWS = 6 };

/* Time the master spent in each part of the window, in any one unit (FRT ticks, cycles): field is the total, the rest are shares of it. */
typedef struct SatReadoutProf { uint32_t field, idle, gfx, sound, tick; } SatReadoutProf;

/* Free running counters kept by the game and the runtime (a wrap is fine: only differences are used). */
typedef struct SatReadoutCounters {
    uint32_t vblanks;           /* vblanks since boot (or since the readout started) */
    uint32_t pictures;          /* new pictures shown: SatVdp1.shown */
    uint32_t missed;            /* game frames not finished when the next vblank came */
    uint32_t flips;             /* game frame starts (an object bank select, a frame counter step) */
    uint32_t skipped;           /* vblanks where the slave was still drawing */
    uint32_t held;              /* frame changes put off because VDP1 had not finished: SatVdp1.waits */
    SatReadoutProf prof;        /* optional; all zero hides the PROF line */
} SatReadoutCounters;

typedef struct SatReadoutCfg {
    const volatile uint8_t *tick_byte;   /* the game's tick counter byte, NULL for no TICK line */
    const char *build_id;                /* short text for the id row, e.g. "F1 a1b2c3", NULL for none */
    uint32_t min_vblanks;                /* shortest window to report, default 30 */
} SatReadoutCfg;

typedef struct SatReadout {
    SatReadoutCfg cfg;
    SatReadoutCounters last;             /* counters at the last report */
    uint8_t tick_last;                   /* the tick byte at the last sat_ro_vblank() */
    uint32_t ticks;                      /* ticks accumulated by sat_ro_vblank() since boot (wrap fine) */
    uint32_t ticks_last;
    uint8_t started;
    char line[SAT_RO_ROWS][SAT_RO_COLS + 16];   /* the text; slack so no line can overrun */
    char shown[SAT_RO_ROWS][SAT_RO_COLS];       /* what the callback has been given (shadow), to send only changes */
} SatReadout;

/* A cell changed: row, column, the character (0 for blank), and whether it is part of a number (a game may draw those in another colour). */
typedef void (*SatReadoutCell)(void *ctx, unsigned row, unsigned col, char ch, int number);

void sat_ro_init(SatReadout *r, const SatReadoutCfg *cfg);
/* Once a vblank, from the master's vblank code: reads the game's tick byte so no tick is lost to its wrap. */
void sat_ro_vblank(SatReadout *r);
/* About once a second (any time; it returns 0 and does nothing until min_vblanks have passed since the last report). Reads the counters, rewrites the lines,
   and returns 1 when a report was made. The first call only starts the window. */
int sat_ro_update(SatReadout *r, const SatReadoutCounters *now);
/* Send every cell that differs from what the callback has already been given (all of them the first time or after sat_ro_invalidate()). */
void sat_ro_paint(SatReadout *r, SatReadoutCell cell, void *ctx);
void sat_ro_invalidate(SatReadout *r);      /* the layer was cleared: the next paint sends everything */

/* The power-up report line into row SAT_RO_ROW_SELFTEST. audio_status is sat_scsp_init()'s *status, with the attempts it returned in the low byte
   (`status | attempts`, as AvP did), and bit 10 if the game read the master volume register back; chips is sat_ro_chip_selftest(). */
void sat_ro_selftest_line(SatReadout *r, unsigned audio_status, unsigned chips);
/* Chip read-back test, after the display is on and the boot display (sat_diag) has ended, because the last VDP2 VRAM bytes are its back screen table: writes and reads back one word of CRAM, VDP2 VRAM and VDP1 VRAM (the last entries, so a picture in
   use is not touched; the words are zeroed after). Returns bits 1 CRAM, 2 VDP2 VRAM, 4 VDP1 VRAM, set = read back as written. Console only. */
unsigned sat_ro_chip_selftest(void);

/* Small helpers, exposed for the tests. */
char *sat_ro_put_num(char *p, uint32_t v);           /* decimal, at most 9999 */
uint32_t sat_ro_per60(uint32_t count, uint32_t vblanks);   /* count scaled to 60 vblanks, rounded */
#endif
