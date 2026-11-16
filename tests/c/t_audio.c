/* Host test: sat_scsp and sat_cdda through fake hardware. */
#define SAT_HOST 1
#include <string.h>
#include "../../saturn/include/sat_hw.h"
#include "../../saturn/audio/sat_scsp.h"
#include "../../saturn/audio/sat_cdda.h"
#include "check.h"

/* ---- SCSP ---- */
static uint16_t slot[32][16]; static uint8_t ram[0x100]; static uint16_t mixer; static int smpc_log[8], smpc_n, fail_first;
static void s_wr(void *c, unsigned n, unsigned r, uint16_t v) { (void)c; slot[n][r / 2] = v; }
static uint16_t s_rd(void *c, unsigned n, unsigned r) { (void)c; return slot[n][r / 2]; }
static void r_wr(void *c, uint32_t o, uint16_t v) { (void)c; ram[o] = (uint8_t)(v >> 8); ram[o + 1] = (uint8_t)v; }
static uint16_t r_rd(void *c, uint32_t o) { (void)c; return (uint16_t)(ram[o] << 8 | ram[o + 1]); }
static void m_wr(void *c, uint16_t v) { (void)c; mixer = v; }
static void sm(void *c, unsigned cmd, int *to) { (void)c; smpc_log[smpc_n++] = (int)cmd; if (fail_first && smpc_n == 1) *to = 1; }
static const SatScspHw hw = { s_wr, s_rd, r_wr, r_rd, m_wr, sm, 0 };

/* ---- CD block ---- */
static uint16_t cd[5], level[2]; static struct { unsigned reg; uint16_t v; } cw[32]; static int cwn;
static uint16_t c_rd(void *c, unsigned r) { (void)c; return cd[r]; }
static void c_wr(void *c, unsigned r, uint16_t v) { (void)c; cw[cwn].reg = r; cw[cwn++].v = v; cd[r] = v; }
static void c_lv(void *c, unsigned in, uint16_t v) { (void)c; level[in] = v; }
static const SatCdHw chw = { c_rd, c_wr, c_lv, 0 };

int main(void)
{
    SatScspVoice v; unsigned st; SatCdda cdda; int i;
    /* rate words: 11025 is octave -2, 8000 is octave -3 with FNS 462, 22050 is octave -1, 44100 is octave 0 (the AvP clip rates) */
    CHECK_EQ(sat_scsp_rate_word(11025), 0xeu << 11); CHECK_EQ(sat_scsp_rate_word(8000), (0xdu << 11) | 462); CHECK_EQ(sat_scsp_rate_word(5513), 0xdu << 11 | 0);
    CHECK_EQ(sat_scsp_rate_word(22050), 0xfu << 11); CHECK_EQ(sat_scsp_rate_word(44100), 0); CHECK_EQ(sat_scsp_rate_word(0), 0);
    CHECK_EQ(sat_scsp_rate_word(66150), 512); CHECK_EQ(sat_scsp_rate_word(88200), 1 << 11);
    /* pan: centre 0x10, left of centre sets bit 4, 15 steps max, mono forces the centre */
    CHECK_EQ(sat_scsp_pan(0x10, 1), 0); CHECK_EQ(sat_scsp_pan(0x0c, 1), 0x14); CHECK_EQ(sat_scsp_pan(0, 1), 0x1f); CHECK_EQ(sat_scsp_pan(0x20, 1), 15); CHECK_EQ(sat_scsp_pan(0x03, 0), 0);
    /* init: SNDOFF, park the 68000, SNDON, mixer, slots clear; the first SMPC wait running out forces a second attempt */
    fail_first = 1; ram[0x10] = 0;
    CHECK_EQ(sat_scsp_init(&hw, &st), 2); CHECK_EQ(smpc_log[0], SAT_SMPC_SNDOFF); CHECK_EQ(smpc_log[1], SAT_SMPC_SNDON); CHECK_EQ(smpc_n, 4);
    CHECK_EQ(st, 0x302u); CHECK_EQ(mixer, 0x020f); CHECK_EQ(ram[0x10], 0x60); CHECK_EQ(ram[0x11], 0xfe); CHECK_EQ(ram[0], 0); CHECK_EQ(ram[1], 7); CHECK_EQ(ram[2], 0xff); CHECK_EQ(ram[3], 0xfc);
    CHECK_EQ(ram[6], 0); CHECK_EQ(ram[7], 0x10); CHECK_EQ(slot[0][0], 0x1000);
    /* samples are written big endian */
    { static const uint8_t d[4] = { 1, 2, 3, 4 }; sat_scsp_write_ram(&hw, 0x40, d, 4); CHECK_EQ(ram[0x40], 1); CHECK_EQ(ram[0x43], 4); }
    /* a one shot and a looping clip on a slot, then stop */
    v.start = 0x12345; v.samples = 70000; v.rate_word = 0xeu << 11; v.tl = 9; v.pan = 0x14; v.loop = 0; v.pcm16 = 0;
    sat_scsp_play(&hw, 3, &v);
    CHECK_EQ(slot[3][0], (uint16_t)(0x0010 | 0x0001 | 0x0800 | 0x1000)); CHECK_EQ(slot[3][1], 0x2345); CHECK_EQ(slot[3][3], 0xffff); CHECK_EQ(slot[3][6], 9);
    CHECK_EQ(slot[3][8], 0xeu << 11); CHECK_EQ(slot[3][0x16 / 2], (uint16_t)(7u << 13 | 0x14u << 8));
    v.loop = 1; sat_scsp_play(&hw, 4, &v); CHECK(slot[4][0] & 0x0020);
    sat_scsp_stop(&hw, 3); CHECK(!(slot[3][0] & 0x0800)); CHECK(slot[3][0] & 0x1000);
    /* ---- CD audio ---- */
    sat_cdda_init(&cdda, &chw, 60);
    sat_cdda_music(&cdda, 4, 5, 150);                     /* intro track 4 for 150 CD frames (2 s = 120 video frames), then track 5 repeating */
    CHECK_EQ(cdda.intro_left, 120); cd[0] = 0;            /* the block is busy: nothing is sent */
    sat_cdda_frame(&cdda); CHECK_EQ(cwn, 0); CHECK_EQ(cdda.want, 1);
    cd[0] = SAT_CD_HIRQ_CMOK; sat_cdda_frame(&cdda);      /* ready: HIRQ cleared first, CR1..CR4 in order, CR4 last */
    CHECK_EQ(cwn, 5); CHECK_EQ(cw[0].reg, 0); CHECK_EQ(cw[0].v, (uint16_t)~SAT_CD_HIRQ_CMOK);
    for (i = 1; i <= 4; i++) CHECK_EQ(cw[i].reg, (unsigned)i);
    CHECK_EQ(cw[1].v, 0x1000); CHECK_EQ(cw[2].v, (4 << 8) | 1); CHECK_EQ(cw[3].v, 0); CHECK_EQ(cw[4].v, (4 << 8) | 99);
    CHECK_EQ(level[0], 7 << 5 | 0x1f); CHECK_EQ(level[1], 7 << 5 | 0x0f);
    /* the intro counts only while the drive reports play, then the loop track starts */
    cwn = 0; cd[0] = SAT_CD_HIRQ_CMOK;
    for (i = 0; i < 119; i++) { cd[1] = (uint16_t)(SAT_CD_STATUS_PLAY << 8); sat_cdda_frame(&cdda); }
    CHECK_EQ(cwn, 0); CHECK_EQ(cdda.loop_next, 5);
    cd[1] = (uint16_t)(SAT_CD_STATUS_PLAY << 8); sat_cdda_frame(&cdda); sat_cdda_frame(&cdda);
    CHECK_EQ(cdda.loop_next, 0); CHECK_EQ(cw[2].v, (5 << 8) | 1); CHECK_EQ(cw[3].v, 0x0f00);
    /* a paused drive does not count the intro */
    sat_cdda_music(&cdda, 4, 5, 75); cd[1] = 0; for (i = 0; i < 200; i++) sat_cdda_frame(&cdda); CHECK_EQ(cdda.loop_next, 5);
    /* fade out: steps down by the rate, ends at 0, the level follows the top three bits; fade in starts from 0 */
    sat_cdda_init(&cdda, &chw, 60); cwn = 0;
    sat_cdda_fade(&cdda, -1, 0x2000); for (i = 0; i < 3; i++) sat_cdda_frame(&cdda);
    CHECK_EQ(cdda.fade_level, 0xffffu - 3 * 0x2000u); CHECK_EQ(level[0] >> 5, 0x9fffu >> 13);
    for (i = 0; i < 10; i++) sat_cdda_frame(&cdda);
    CHECK_EQ(cdda.fade_level, 0); CHECK_EQ(cdda.fade_dir, 0);
    sat_cdda_fade(&cdda, 1, 0x4000); CHECK_EQ(cdda.fade_level, 0); sat_cdda_fade(&cdda, 1, 0x8000); CHECK_EQ(cdda.fade_rate, 0x4000);   /* already going this way: ignored */
    /* a data load took the drive: queued work is dropped and the level is written again */
    sat_cdda_pause(&cdda); CHECK_EQ(cdda.want, 1); level[0] = 0; sat_cdda_after_load(&cdda); CHECK_EQ(cdda.want, 0); CHECK_EQ(level[0] >> 5, cdda.fade_level >> 13);
    PASS();
}
