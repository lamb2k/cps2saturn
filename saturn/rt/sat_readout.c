/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn release/v0.1.2-beta, saturn/rt/fps_hud.c. See sat_readout.h. */
#include "sat_readout.h"
#include "../include/sat_hw.h"

static char *put_str(char *p, const char *s) { while (*s) *p++ = *s++; return p; }

char *sat_ro_put_num(char *p, uint32_t v)
{
    char t[8];
    int n = 0;
    if (v > 9999) v = 9999;
    do { t[n++] = (char)('0' + v % 10); v /= 10; } while (v);
    while (n) *p++ = t[--n];
    return p;
}

uint32_t sat_ro_per60(uint32_t count, uint32_t vblanks)
{
    return vblanks ? (count * 60u + (vblanks >> 1)) / vblanks : 0;
}

static void fill(void *dst, uint8_t v, unsigned bytes)   /* the runtime links without a C library */
{
    volatile uint8_t *d = (volatile uint8_t *)dst;
    while (bytes--) *d++ = v;
}

void sat_ro_init(SatReadout *r, const SatReadoutCfg *cfg)
{
    fill(r, 0, sizeof *r);
    r->cfg = *cfg;
    if (!r->cfg.min_vblanks) r->cfg.min_vblanks = 30;
    sat_ro_invalidate(r);
}

void sat_ro_invalidate(SatReadout *r)
{
    fill(r->shown, 0xff, sizeof r->shown);
}

void sat_ro_vblank(SatReadout *r)
{
    uint8_t b;
    if (!r->cfg.tick_byte) return;
    b = *r->cfg.tick_byte;
    r->ticks += (uint8_t)(b - r->tick_last);
    r->tick_last = b;
}

static void clear_rows(SatReadout *r)
{
    unsigned i;
    for (i = 0; i < SAT_RO_ROWS; i++) r->line[i][0] = 0;
}

int sat_ro_update(SatReadout *r, const SatReadoutCounters *now)
{
    uint32_t dv, over, flips, skips, waits, shown, ticks;
    char *p;
    if (!r->started) {   /* the first call opens the window; the tick byte is read now so its first step is not a jump */
        r->started = 1;
        r->last = *now;
        r->ticks_last = r->ticks;
        if (r->cfg.tick_byte) r->tick_last = *r->cfg.tick_byte;
        clear_rows(r);
        p = put_str(r->line[SAT_RO_ROW_PIC], "PIC");   /* alive, no numbers yet */
        *p = 0;
        return 0;
    }
    dv = now->vblanks - r->last.vblanks;
    if (dv < r->cfg.min_vblanks) return 0;
    shown = now->pictures - r->last.pictures;
    over = now->missed - r->last.missed;
    flips = now->flips - r->last.flips;
    skips = now->skipped - r->last.skipped;
    waits = now->held - r->last.held;
    ticks = r->ticks - r->ticks_last;

    p = put_str(r->line[SAT_RO_ROW_PIC], "PIC "); p = sat_ro_put_num(p, sat_ro_per60(shown, dv));
    p = put_str(p, " DONE "); p = sat_ro_put_num(p, sat_ro_per60(over >= dv ? 0 : dv - over, dv)); *p = 0;
    p = put_str(r->line[SAT_RO_ROW_MISS], "MISS "); p = sat_ro_put_num(p, over);
    p = put_str(p, " SKIP "); p = sat_ro_put_num(p, skips);
    p = put_str(p, " HELD "); p = sat_ro_put_num(p, waits); *p = 0;
    p = r->line[SAT_RO_ROW_ID];
    if (r->cfg.build_id) { p = put_str(p, r->cfg.build_id); *p++ = ' '; }
    p = put_str(p, "FLIP "); p = sat_ro_put_num(p, sat_ro_per60(flips, dv)); p = put_str(p, " VBL "); p = sat_ro_put_num(p, dv); *p = 0;
    if (r->cfg.tick_byte) { p = put_str(r->line[SAT_RO_ROW_TICK], "TICK "); p = sat_ro_put_num(p, sat_ro_per60(ticks, dv)); *p = 0; }
    {   /* PROF: percent of the field */
        const SatReadoutProf *a = &now->prof, *b = &r->last.prof;
        uint32_t f = a->field - b->field;
        if (f) {
            uint32_t t = a->tick - b->tick, g = a->gfx - b->gfx, s = a->sound - b->sound, id = a->idle - b->idle;
            uint32_t o = f > id + t + g + s ? f - id - t - g - s : 0;
#define PCT(x) (((x) * 100u + (f >> 1)) / f)
            p = put_str(r->line[SAT_RO_ROW_PROF], "PROF T"); p = sat_ro_put_num(p, PCT(t));
            p = put_str(p, " G"); p = sat_ro_put_num(p, PCT(g));
            p = put_str(p, " S"); p = sat_ro_put_num(p, PCT(s));
            p = put_str(p, " O"); p = sat_ro_put_num(p, PCT(o));
            p = put_str(p, " I"); p = sat_ro_put_num(p, PCT(id)); *p = 0;
#undef PCT
        }
    }
    r->last = *now;
    r->ticks_last = r->ticks;
    return 1;
}

void sat_ro_selftest_line(SatReadout *r, unsigned audio_status, unsigned chips)
{
    char *p = put_str(r->line[SAT_RO_ROW_SELFTEST], "HW SND ");
    p = sat_ro_put_num(p, audio_status & 0xffu);
    p = put_str(p, (audio_status & 0x100u) ? " OK" : " NO");
    if (audio_status & 0x200u) p = put_str(p, " TMO");
    if (audio_status & 0x400u) p = put_str(p, " RB");
    p = put_str(p, " TEST ");
    p = sat_ro_put_num(p, chips);
    *p = 0;
}

void sat_ro_paint(SatReadout *r, SatReadoutCell cell, void *ctx)
{
    unsigned row, col;
    for (row = 0; row < SAT_RO_ROWS; row++) {
        int num = 0;
        for (col = 0; col < SAT_RO_COLS; col++) {
            char ch = r->line[row][col], out;
            if (ch == 0 || ch == ' ') { out = 0; num = 0; }
            else { out = ch; num = ch >= '0' && ch <= '9'; }   /* a run of digits is a number */
            if (r->shown[row][col] != out) {
                r->shown[row][col] = out;
                cell(ctx, row, col, out, num);
            }
            if (ch == 0) {   /* the rest of the line is blank: send the blanks, then stop reading text */
                for (col++; col < SAT_RO_COLS; col++) if (r->shown[row][col] != 0) { r->shown[row][col] = 0; cell(ctx, row, col, 0, 0); }
                break;
            }
        }
    }
}

#ifndef SAT_HOST
unsigned sat_ro_chip_selftest(void)
{
    unsigned ok = 0;
    volatile uint16_t *cr = (volatile uint16_t *)(SAT_VDP2_CRAM + 2047u * 2u);
    volatile uint16_t *v2 = (volatile uint16_t *)(SAT_VDP2_VRAM + 0x7ff80u);
    volatile uint16_t *v1 = (volatile uint16_t *)(SAT_VDP1_VRAM + 0x7ff80u);
    *cr = 0x5aa5; *v2 = 0x5aa5; *v1 = 0x5aa5;
    if (*cr == 0x5aa5) ok |= 1;
    if (*v2 == 0x5aa5) ok |= 2;
    if (*v1 == 0x5aa5) ok |= 4;
    *cr = 0; *v2 = 0; *v1 = 0;
    return ok;
}
#endif
