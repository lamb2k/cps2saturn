/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/gfx/sat_gfx.c (sat_gfx_vblank, plot_wait_end, plot_wait_shown, plot_start, the table setup of sat_gfx_init).
 * The hardware-erase experiment and the diagnostics stayed in AvP. See sat_vdp1.h. */
#include "sat_vdp1.h"

#define REG(v, o) ((v)->regs[(o) / 2])
#define UNC(x) SAT_UNC32(x)

#ifdef SAT_HOST
static void put16(volatile uint8_t *p, uint16_t x) { p[0] = (uint8_t)(x >> 8); p[1] = (uint8_t)x; }   /* the host's VRAM is a plain byte array, big endian */
#define W16(p, x) put16((p), (x))
#else
#define W16(p, x) (*(volatile uint16_t *)(void *)(p) = (uint16_t)(x))
#endif

void sat_v1_init(SatVdp1 *v, volatile uint8_t *vram, volatile uint16_t *regs, uint32_t table_a, uint32_t table_b,
                 unsigned screen_w, unsigned screen_h, uint32_t (*ticks)(void))
{
    unsigned t;
    v->vram = vram; v->regs = regs; v->table[0] = table_a; v->table[1] = table_b; v->cur = 0;
    v->started = v->shown = v->held = v->sync = v->waits = 0;
    v->cef_asked = v->cef_forced = v->replots = v->kicked = 0;
    v->wait_max = SAT_SLAVE_WAIT_MAX; v->ticks = ticks; v->prev = 0;
    REG(v, SAT_VDP1_TVMR) = 0;
    REG(v, SAT_VDP1_EWDR) = 0;
    REG(v, SAT_VDP1_EWLR) = 0;
    REG(v, SAT_VDP1_EWRR) = (uint16_t)(((screen_w >> 3) << 9) | (screen_h - 1));
    W16(vram + 0, 0x0009);                 /* system clip, set to the whole screen */
    W16(vram + 20, screen_w - 1);
    W16(vram + 22, screen_h - 1);
    for (t = 0; t < 2; t++) {
        W16(vram + v->table[t] + 32, 0x000a);                         /* local origin 0, 0 */
        W16(vram + v->table[t] + SAT_V1_FIRST_CMD, SAT_V1_END_CODE);  /* an empty list */
    }
    REG(v, SAT_VDP1_PTMR) = 0;
}

volatile uint8_t *sat_v1_cmd(SatVdp1 *v) { return v->vram + v->table[v->cur] + SAT_V1_FIRST_CMD; }
volatile uint8_t *sat_v1_clear(volatile uint8_t *cmd, unsigned w, unsigned h)
{
    unsigned i;
    W16(cmd + 0, 0x0004);                  /* polygon, next command follows */
    W16(cmd + 2, 0);
    W16(cmd + 4, 0x00c0);                  /* ECD and SPD: colour 0 is written, not skipped */
    W16(cmd + 6, 0);                       /* colour 0 = clear in the sprite types that treat 0 as transparent */
    for (i = 8; i < 12; i += 2) W16(cmd + i, 0);
    W16(cmd + 12, 0); W16(cmd + 14, 0);                    /* A (0, 0) */
    W16(cmd + 16, w - 1); W16(cmd + 18, 0);                /* B (w-1, 0) */
    W16(cmd + 20, w - 1); W16(cmd + 22, h - 1);            /* C (w-1, h-1) */
    W16(cmd + 24, 0); W16(cmd + 26, h - 1);                /* D (0, h-1) */
    W16(cmd + 28, 0); W16(cmd + 30, 0);
    return cmd + SAT_V1_CMD_BYTES;
}
void sat_v1_end(SatVdp1 *v, volatile uint8_t *after_last) { (void)v; W16(after_last, SAT_V1_END_CODE); }

void sat_v1_vblank(SatVdp1 *v)
{
    uint32_t s = UNC(v->started);
    UNC(v->sync) = 1;
    if (s != UNC(v->shown)) {
        if (REG(v, SAT_VDP1_EDSR) & SAT_EDSR_CEF) {
            REG(v, SAT_VDP1_FBCR) = 3;      /* change, erase and draw at the change */
            UNC(v->shown) = s;
            UNC(v->held) = 0;
        } else {
            UNC(v->held) = UNC(v->held) + 1;
            UNC(v->waits) = UNC(v->waits) + 1;
        }
    }
}

int sat_v1_wait_end(SatVdp1 *v)
{
    uint32_t t0 = v->ticks();
    if (!UNC(v->sync)) return 1;
    while (UNC(v->started) != UNC(v->shown) && !(REG(v, SAT_VDP1_EDSR) & SAT_EDSR_CEF))
        if (((v->ticks() - t0) & 0xffffu) > v->wait_max) {
            /* A plot was started and its end flag never came for two frames: VDP1's state was replaced under it. The master asks for the change only
               after the end flag, so without this the slave would abandon every picture from here on. Start the same list again, once for each
               plot (its table and textures are untouched: this slave has not written since), and wait one more bound. A plot that is only slow is
               not started a second time, so it still finishes. */
            if (v->kicked != UNC(v->started)) {
                v->kicked = UNC(v->started);
                REG(v, SAT_VDP1_PTMR) = 1; t0 = v->ticks(); v->replots++;
                continue;
            }
            return 0;
        }
    return 1;
}

static int wait_shown(SatVdp1 *v)
{
    uint32_t t0 = v->ticks();
    while (UNC(v->started) != UNC(v->shown))
        if (((v->ticks() - t0) & 0xffffu) > v->wait_max) return 0;
    return 1;
}

int sat_v1_plot(SatVdp1 *v)
{
    uint32_t base = v->table[v->cur];
    /* The first list ever, or before the master's first vblank hook (standalone and host builds): the old path, change asked for at the plot. */
    W16(v->vram + 0 + 0, 0x1009);                              /* system clip with a jump (assign) to the table in use */
    W16(v->vram + 2, (uint16_t)((base + 0x20) >> 3));
    if (!UNC(v->sync)) {
        REG(v, SAT_VDP1_FBCR) = 3; REG(v, SAT_VDP1_PTMR) = 1;
        v->prev = 1; v->cur ^= 1;      /* not counted in started: the master has nothing to confirm yet */
        return 1;
    }
    if (!wait_shown(v)) return 0;
    /* The plot goes into the back buffer only once the change has really happened. */
    if (v->prev) {
        uint32_t t0 = v->ticks();
        int asked = 0;
        while (REG(v, SAT_VDP1_EDSR) & SAT_EDSR_CEF)
            if (((v->ticks() - t0) & 0xffffu) >= v->wait_max) {
                /* CEF still set and no change pending (every plot started has been shown, so the master asked for its change): the change was
                   never latched or the chip state was replaced. Ask for the change ourselves once and wait one more bound, then plot anyway:
                   a lost or one-off wrong picture instead of a stalled slave. */
                if (!asked) { asked = 1; REG(v, SAT_VDP1_FBCR) = 3; t0 = v->ticks(); v->cef_asked++; continue; }
                v->cef_forced++;
                break;
            }
    }
    REG(v, SAT_VDP1_PTMR) = 1;
    UNC(v->started) = UNC(v->started) + 1;
    v->prev = 1; v->cur ^= 1;
    return 1;
}
