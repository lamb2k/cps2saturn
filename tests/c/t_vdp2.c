/* Host test: sat_vdp2 latch, layout, helpers, and sat_scsp rate words are in t_audio.c. */
#define SAT_HOST 1
#include <string.h>
#include "../../saturn/gfx/sat_vdp2.h"
#include "check.h"

static uint16_t regs[0x90]; static SatV2Latch L;
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
    PASS();
}
