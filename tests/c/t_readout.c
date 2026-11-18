/* Host test: sat_readout, the console readout text. Counters in, lines and changed cells out. */
#include <string.h>
#define SAT_HOST 1
#include "../../saturn/rt/sat_readout.h"
#include "check.h"

static int cells, numbers;
static char grid[SAT_RO_ROWS][SAT_RO_COLS];
static void put(void *ctx, unsigned row, unsigned col, char ch, int number)
{
    (void)ctx; cells++; if (number) numbers++;
    grid[row][col] = ch;
}
static void row_text(unsigned row, char *out)
{
    unsigned c;
    for (c = 0; c < SAT_RO_COLS; c++) out[c] = grid[row][c] ? grid[row][c] : ' ';
    out[SAT_RO_COLS] = 0;
    for (c = SAT_RO_COLS; c > 0 && out[c - 1] == ' '; c--) out[c - 1] = 0;
}

static volatile uint8_t tick_byte;
static SatReadout ro;

int main(void)
{
    SatReadoutCfg cfg = { &tick_byte, "F1 a1b2", 0 };
    SatReadoutCounters n;
    char t[SAT_RO_COLS + 1];
    unsigned i;

    /* helpers */
    { char b[8], *p = sat_ro_put_num(b, 0); *p = 0; CHECK(!strcmp(b, "0")); p = sat_ro_put_num(b, 60); *p = 0; CHECK(!strcmp(b, "60"));
      p = sat_ro_put_num(b, 123456); *p = 0; CHECK(!strcmp(b, "9999")); }
    CHECK_EQ(sat_ro_per60(30, 60), 30); CHECK_EQ(sat_ro_per60(7, 30), 14); CHECK_EQ(sat_ro_per60(5, 0), 0);

    memset(&n, 0, sizeof n);
    memset(grid, 0, sizeof grid);
    sat_ro_init(&ro, &cfg);
    CHECK_EQ(ro.cfg.min_vblanks, 30);
    /* the first call opens the window and shows only "PIC" */
    CHECK_EQ(sat_ro_update(&ro, &n), 0);
    cells = 0; sat_ro_paint(&ro, put, 0);
    row_text(SAT_RO_ROW_PIC, t); CHECK(!strcmp(t, "PIC"));
    CHECK_EQ(cells, SAT_RO_ROWS * SAT_RO_COLS);   /* everything sent once: blanks included */
    cells = 0; sat_ro_paint(&ro, put, 0); CHECK_EQ(cells, 0);   /* nothing changed: nothing sent */

    /* 100 vblanks in which the game ticks 3 a vblank (a byte that wraps at 256, 300 ticks), the tick the master, 90 pictures, 10 missed frames */
    for (i = 0; i < 100; i++) { tick_byte = (uint8_t)(tick_byte + 3); sat_ro_vblank(&ro); n.vblanks++; if (i == 20) { CHECK_EQ(sat_ro_update(&ro, &n), 0); } }   /* 21 vblanks: too soon */
    n.pictures = 90; n.missed = 10; n.flips = 100; n.skipped = 4; n.held = 2;
    n.prof.field = 1000; n.prof.tick = 300; n.prof.gfx = 200; n.prof.sound = 50; n.prof.idle = 250;
    CHECK_EQ(sat_ro_update(&ro, &n), 1);
    cells = numbers = 0; sat_ro_paint(&ro, put, 0);
    row_text(SAT_RO_ROW_PIC, t); CHECK(!strcmp(t, "PIC 54 DONE 54"));           /* 90 per 100 vblanks = 54 a 60; (100 - 10) = 54 */
    row_text(SAT_RO_ROW_MISS, t); CHECK(!strcmp(t, "MISS 10 SKIP 4 HELD 2"));
    row_text(SAT_RO_ROW_ID, t); CHECK(!strcmp(t, "F1 a1b2 FLIP 60 VBL 100"));
    row_text(SAT_RO_ROW_TICK, t); CHECK(!strcmp(t, "TICK 180"));                 /* 300 ticks in 100 vblanks is 180 a 60 */
    row_text(SAT_RO_ROW_PROF, t); CHECK(!strcmp(t, "PROF T30 G20 S5 O20 I25"));  /* 1000 field: 300 tick, 200 gfx, 50 sound, 250 idle, the other 200 is O */
    CHECK(cells > 0 && numbers > 0);
    /* a second window with the same game speed and fewer pictures: only the changed cells go out */
    for (i = 0; i < 60; i++) { tick_byte = (uint8_t)(tick_byte + 1); sat_ro_vblank(&ro); n.vblanks++; }
    n.pictures += 30; n.flips += 60; n.prof.field += 600; n.prof.tick += 600;
    CHECK_EQ(sat_ro_update(&ro, &n), 1);
    cells = 0; sat_ro_paint(&ro, put, 0);
    row_text(SAT_RO_ROW_TICK, t); CHECK(!strcmp(t, "TICK 60"));
    row_text(SAT_RO_ROW_PROF, t); CHECK(!strcmp(t, "PROF T100 G0 S0 O0 I0"));
    CHECK(cells > 0 && cells < SAT_RO_ROWS * SAT_RO_COLS);
    row_text(SAT_RO_ROW_PIC, t); CHECK(!strcmp(t, "PIC 30 DONE 60"));
    row_text(SAT_RO_ROW_MISS, t); CHECK(!strcmp(t, "MISS 0 SKIP 0 HELD 0"));     /* a shorter line blanks the cells the longer one left */
    row_text(SAT_RO_ROW_ID, t); CHECK(!strcmp(t, "F1 a1b2 FLIP 60 VBL 60"));
    /* the layer was cleared: everything is sent again */
    sat_ro_invalidate(&ro); cells = 0; sat_ro_paint(&ro, put, 0); CHECK_EQ(cells, SAT_RO_ROWS * SAT_RO_COLS);
    /* a game with no tick byte has no TICK line; a game with no time counters has no PROF line */
    { SatReadout r2; SatReadoutCfg c2 = { 0, 0, 10 }; SatReadoutCounters m; memset(&m, 0, sizeof m); sat_ro_init(&r2, &c2);
      sat_ro_update(&r2, &m); m.vblanks = 10; m.pictures = 10; CHECK_EQ(sat_ro_update(&r2, &m), 1);
      CHECK_EQ(r2.line[SAT_RO_ROW_TICK][0], 0); CHECK_EQ(r2.line[SAT_RO_ROW_PROF][0], 0); CHECK(!strcmp(r2.line[SAT_RO_ROW_ID], "FLIP 0 VBL 10")); }
    /* the power-up report line */
    sat_ro_selftest_line(&ro, 0x100u | 1u, 7); CHECK(!strcmp(ro.line[SAT_RO_ROW_SELFTEST], "HW SND 1 OK TEST 7"));
    sat_ro_selftest_line(&ro, 0x200u | 0x400u | 3u, 5); CHECK(!strcmp(ro.line[SAT_RO_ROW_SELFTEST], "HW SND 3 NO TMO RB TEST 5"));
    PASS();
}
