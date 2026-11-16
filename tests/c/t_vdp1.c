/* Host test: sat_vdp1, the plot / frame change protocol. VDP1 registers and VRAM are arrays; the slave's timer advances 100 ticks a call. */
#include <string.h>
#define SAT_HOST 1
#include "../../saturn/gfx/sat_vdp1.h"
#include "check.h"

static uint16_t regs[0x20]; static uint8_t vram[0x10000]; static uint32_t now;
static uint32_t ticks(void) { return now += 100; }
#define R(o) regs[(o) / 2]
static SatVdp1 v;
static void fresh(void) { memset(regs, 0, sizeof regs); memset(vram, 0, sizeof vram); now = 0; sat_v1_init(&v, vram, regs, 0x0000, 0x8000, 352, 224, ticks); v.wait_max = 1000; }

int main(void)
{
    volatile uint8_t *c;
    fresh();
    /* tables set up: system clip, local origin, empty list, end of list */
    CHECK_EQ((vram[0] << 8) | vram[1], 0x0009); CHECK_EQ((vram[20] << 8) | vram[21], 351); CHECK_EQ((vram[22] << 8) | vram[23], 223);
    CHECK_EQ((vram[0x8020] << 8) | vram[0x8021], 0x000a); CHECK_EQ((vram[0x8040] << 8) | vram[0x8041], 0x8000);
    CHECK_EQ(R(SAT_VDP1_EWRR), (352 / 8) << 9 | 223);
    /* before the master's first vblank hook: the plot asks for the change itself, the table flips, nothing is counted */
    c = sat_v1_cmd(&v); CHECK(c == vram + 0x40);
    CHECK_EQ(sat_v1_wait_end(&v), 1);
    CHECK_EQ(sat_v1_plot(&v), 1); CHECK_EQ(R(SAT_VDP1_FBCR), 3); CHECK_EQ(R(SAT_VDP1_PTMR), 1); CHECK_EQ(v.started, 0);
    CHECK_EQ((vram[0] << 8) | vram[1], 0x1009); CHECK_EQ((vram[2] << 8) | vram[3], 0x20 >> 3);   /* jump to table A's local origin */
    c = sat_v1_cmd(&v); CHECK(c == vram + 0x8040);
    /* synchronized: the slave starts a plot, the master confirms it only when VDP1 reports the end */
    sat_v1_vblank(&v); CHECK_EQ(v.sync, 1); CHECK_EQ(v.started, v.shown);
    R(SAT_VDP1_FBCR) = 0; R(SAT_VDP1_PTMR) = 0; R(SAT_VDP1_EDSR) = 0;
    CHECK_EQ(sat_v1_wait_end(&v), 1);
    CHECK_EQ(sat_v1_plot(&v), 0 + 1 - 0 == 1 ? 1 : 0);
    CHECK_EQ(v.started, 1); CHECK_EQ(R(SAT_VDP1_PTMR), 1);
    CHECK_EQ((vram[2] << 8 | vram[3]), (0x8000 + 0x20) >> 3);
    R(SAT_VDP1_EDSR) = 0;                                      /* still plotting at the vblank: hold the old picture */
    R(SAT_VDP1_FBCR) = 0; sat_v1_vblank(&v); CHECK_EQ(R(SAT_VDP1_FBCR), 0); CHECK_EQ(v.shown, 0); CHECK_EQ(v.held, 1); CHECK_EQ(v.waits, 1);
    R(SAT_VDP1_EDSR) = SAT_EDSR_CEF; sat_v1_vblank(&v);        /* the end flag is up: the change is asked for */
    CHECK_EQ(R(SAT_VDP1_FBCR), 3); CHECK_EQ(v.shown, 1); CHECK_EQ(v.held, 0);
    /* the next plot waits for the change to latch (CEF clear), then starts */
    R(SAT_VDP1_EDSR) = 0; CHECK_EQ(sat_v1_wait_end(&v), 1);
    CHECK_EQ(sat_v1_plot(&v), 1); CHECK_EQ(v.started, 2);
    /* a plot whose end flag never comes: the slave starts it again once, then gives up on this picture */
    R(SAT_VDP1_PTMR) = 0; R(SAT_VDP1_EDSR) = 0;
    CHECK_EQ(sat_v1_wait_end(&v), 0); CHECK_EQ(v.replots, 1); CHECK_EQ(R(SAT_VDP1_PTMR), 1);
    CHECK_EQ(sat_v1_wait_end(&v), 0); CHECK_EQ(v.replots, 1);   /* the same plot is not started a second time */
    /* a change that never latched: CEF stays up although every plot is shown; the slave asks once, then plots anyway */
    fresh(); sat_v1_vblank(&v); CHECK_EQ(sat_v1_plot(&v), 1);
    R(SAT_VDP1_EDSR) = SAT_EDSR_CEF; sat_v1_vblank(&v); CHECK_EQ(v.shown, v.started);
    R(SAT_VDP1_FBCR) = 0; CHECK_EQ(sat_v1_plot(&v), 1); CHECK_EQ(v.cef_asked, 1); CHECK_EQ(v.cef_forced, 1); CHECK_EQ(R(SAT_VDP1_FBCR), 3);
    /* the change never confirmed (master never shows it): the slave times out and the caller keeps its texture protection */
    fresh(); sat_v1_vblank(&v); CHECK_EQ(sat_v1_plot(&v), 1); CHECK_EQ(sat_v1_plot(&v), 0);
    /* the clear polygon: polygon command, ECD and SPD, colour 0, corners (0,0) (351,0) (351,223) (0,223), 32 bytes, returns the next slot */
    fresh(); c = sat_v1_clear(vram + 0x40, 352, 224); CHECK(c == vram + 0x60);
    CHECK_EQ((vram[0x40] << 8) | vram[0x41], 0x0004); CHECK_EQ((vram[0x44] << 8) | vram[0x45], 0x00c0); CHECK_EQ((vram[0x46] << 8) | vram[0x47], 0);
    CHECK_EQ((vram[0x50] << 8) | vram[0x51], 351); CHECK_EQ((vram[0x54] << 8) | vram[0x55], 351); CHECK_EQ((vram[0x56] << 8) | vram[0x57], 223); CHECK_EQ((vram[0x5a] << 8) | vram[0x5b], 223);
    PASS();
}
