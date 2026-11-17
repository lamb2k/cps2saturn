/* Host test: sat_vdp2 latch, layout, helpers, and sat_scsp rate words are in t_audio.c. */
#define SAT_HOST 1
#include <string.h>
#include "../../saturn/gfx/sat_vdp2.h"
#include "check.h"

static uint16_t regs[0x90]; static SatV2Latch L; static SatV2Gate G; static uint16_t cram[4096];
static int hook_calls;
static void bump(SatV2Latch *l) { hook_calls++; if (hook_calls == 1) { l->seq += 2; } }   /* a publish landed during the copy: the apply must re-read */

int main(void)
{
    SatVdp2Layout lay = { 0x1300, { 1, 2, 3, 4, 5, 6, 7, 8 }, 0x0101, 0x0000, { 0, 0, 0, 0x8063 }, 0x000f, { 0x3c3c, 0x0c08, 0x0101, 0x0f0f }, { 0x3c3c, 0x1410, 0x0101, 0x0f0f }, 0x0101, { 1, 1 }, { 0x1700, 0x1700 } };
    uint32_t shadow = 5; uint8_t vram[8] = { 0 };
    sat_v2l_init(&L, regs);
    /* nothing published: nothing applied */
    sat_v2l_apply(&L); CHECK_EQ(L.skips, 0); CHECK_EQ(regs[0x20 / 2], 0);
    sat_v2l_write(&L, 0x20, 0x0007); sat_v2l_write(&L, 0x70, 0x1234);
    sat_v2l_apply(&L); CHECK_EQ(regs[0x20 / 2], 0);               /* written but not published */
    sat_v2l_publish(&L); CHECK_EQ(L.seq, 2);
    sat_v2l_apply(&L); CHECK_EQ(regs[0x20 / 2], 7); CHECK_EQ(regs[0x70 / 2], 0x1234); CHECK_EQ(regs[0x72 / 2], 0);   /* only the registers the draw wrote */
    /* a record being published (odd sequence): four tries, nothing written, counted */
    regs[0x20 / 2] = 0; L.seq = 3; sat_v2l_apply(&L); CHECK_EQ(regs[0x20 / 2], 0); CHECK_EQ(L.skips, 1); CHECK_EQ(L.retries, 4);
    /* a publish landing during the copy: that copy is thrown away and read again */
    L.seq = 4; L.retries = 0; L.mid_copy = bump; hook_calls = 0; sat_v2l_apply(&L);
    CHECK_EQ(L.retries, 1); CHECK_EQ(regs[0x20 / 2], 7); CHECK_EQ(hook_calls, 2);
    /* layout */
    memset(regs, 0, sizeof regs); sat_vdp2_layout_apply(regs, &lay);
    CHECK_EQ(regs[0x0e / 2], 0x1300); CHECK_EQ(regs[0x10 / 2], 1); CHECK_EQ(regs[0x1e / 2], 8); CHECK_EQ(regs[0x28 / 2], 0x0101);
    CHECK_EQ(regs[0x36 / 2], 0x8063); CHECK_EQ(regs[0x3a / 2], 0x000f); CHECK_EQ(regs[0x4c / 2], 0x0f0f); CHECK_EQ(regs[0x4e / 2], 0x0f0f);
    CHECK_EQ(regs[0x46 / 2], 0x1410); CHECK_EQ(regs[0x7a / 2], 0x1700); CHECK_EQ(regs[0x8a / 2], 0x1700); CHECK_EQ(regs[0x7c / 2], 1); CHECK_EQ(regs[0x98 / 2], 0x0101);
    sat_vdp2_set_back(regs, 0x1fffe); CHECK_EQ(regs[0xac / 2], 0); CHECK_EQ(regs[0xae / 2], 0xffff);
    sat_vdp2_set_back(regs, 0x7fffe); CHECK_EQ(regs[0xac / 2], 3);
    /* shadow write */
    CHECK_EQ(sat_shadow_write32(vram, 5, &shadow), 0); CHECK_EQ(vram[0], 0);
    CHECK_EQ(sat_shadow_write32(vram, 0x01020304, &shadow), 1); CHECK_EQ(shadow, 0x01020304u);
    CHECK_EQ(sat_shadow_write32(vram, 0x01020304, &shadow), 0);
    /* picture gate (lane vsync): the registers and the queued colour writes of picture s are applied only when s is the picture shown */
    memset(regs, 0, sizeof regs); memset(cram, 0, sizeof cram);
    sat_v2l_init(&L, regs); sat_v2g_init(&G, &L, cram, 1);
    sat_v2l_write(&L, 0x20, 0x000f); sat_v2l_write(&L, 0x70, 0x0100);
    sat_v2g_cram(&G, 3, 0x8001); sat_v2g_cram(&G, 4, 0x8002);
    CHECK_EQ(cram[3], 0);                                         /* queued, not written at draw time */
    sat_v2g_publish(&G, 1);
    sat_v2g_apply(&G, 0); CHECK_EQ(regs[0x20 / 2], 0); CHECK_EQ(cram[3], 0);   /* picture 1 is not shown yet */
    sat_v2g_check(&G, 1, 0); CHECK_EQ(G.chk_n, 1); CHECK_EQ(G.chk_diff, 1); CHECK_EQ(G.chk_behind, 1);
    sat_v2g_apply(&G, 1); CHECK_EQ(regs[0x20 / 2], 0x000f); CHECK_EQ(regs[0x70 / 2], 0x0100); CHECK_EQ(cram[3], 0x8001); CHECK_EQ(cram[4], 0x8002); CHECK_EQ(G.applied, 1);
    sat_v2g_check(&G, 1, 1); CHECK_EQ(G.chk_diff, 1);
    /* picture 2 built and published while picture 1 is still shown: nothing changes until its own change */
    sat_v2l_write(&L, 0x70, 0x0200); sat_v2g_cram(&G, 3, 0x8009); sat_v2g_publish(&G, 2);
    sat_v2g_apply(&G, 1); CHECK_EQ(regs[0x70 / 2], 0x0100); CHECK_EQ(cram[3], 0x8001);
    sat_v2g_apply(&G, 2); CHECK_EQ(regs[0x70 / 2], 0x0200); CHECK_EQ(cram[3], 0x8009); CHECK_EQ(G.applied, 2);
    /* picture 3 published after its plot ended and was shown: the record is not there yet at the change, it is applied at the next V-blank */
    sat_v2g_apply(&G, 3); CHECK_EQ(G.applied, 2);
    sat_v2g_check(&G, 3, 3); CHECK_EQ(G.chk_behind, 2);
    sat_v2l_write(&L, 0x70, 0x0300); sat_v2g_publish(&G, 3); sat_v2g_apply(&G, 3); CHECK_EQ(regs[0x70 / 2], 0x0300);
    /* the same picture twice: the first publish (while building, serial started + 1) is replaced by the final one */
    sat_v2l_write(&L, 0x70, 0x0301); sat_v2g_publish(&G, 4); sat_v2l_write(&L, 0x70, 0x0302); sat_v2g_publish(&G, 4);
    sat_v2g_apply(&G, 4); CHECK_EQ(regs[0x70 / 2], 0x0302);
    /* urgent record: applied at the next V-blank whatever the picture; a record published before it cannot undo it */
    sat_v2l_write(&L, 0x70, 0x0400); sat_v2g_publish(&G, 5);
    sat_v2l_write(&L, 0x20, 0x0008); sat_v2g_urgent(&G);
    sat_v2g_apply(&G, 4); CHECK_EQ(regs[0x20 / 2], 8);
    sat_v2g_apply(&G, 5); CHECK_EQ(regs[0x20 / 2], 8);            /* picture 5's own registers are skipped (layers stay off) */
    sat_v2l_write(&L, 0x20, 0x000f); sat_v2g_publish(&G, 6); sat_v2g_apply(&G, 6); CHECK_EQ(regs[0x20 / 2], 0x000f);
    /* old order: the newest record at the next V-blank, colour writes straight through */
    G.gated = 0; sat_v2l_write(&L, 0x70, 0x0500); sat_v2g_cram(&G, 7, 0x8007); CHECK_EQ(cram[7], 0x8007);
    sat_v2g_publish(&G, 7); sat_v2g_apply(&G, 6); CHECK_EQ(regs[0x70 / 2], 0x0500); CHECK_EQ(G.applied, 7);
    sat_v2g_check(&G, 7, 6); CHECK_EQ(G.chk_ahead, 1);
    /* a full queue: the writer waits, then writes straight through (counted) */
    G.gated = 1; { unsigned i; for (i = 0; i < SAT_V2G_CRAMQ; i++) sat_v2g_cram(&G, 10, 0x8000 | i); }
    CHECK_EQ(G.cq_direct, 0); CHECK_EQ(G.cq_max, SAT_V2G_CRAMQ);
    sat_v2g_cram(&G, 11, 0x8abc); CHECK_EQ(G.cq_direct, 1); CHECK_EQ(cram[11], 0x8abc);
    PASS();
}
