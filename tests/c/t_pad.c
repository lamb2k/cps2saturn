/* Host test: sat_pad's INTBACK sequence through a logging SMPC. */
#define SAT_HOST 1
#include <string.h>
#include "../../saturn/rt/sat_pad.h"
#include "check.h"

static uint8_t reg[0x80]; static int log_n; static struct { unsigned off; uint8_t v; } wlog[32];
static uint8_t rd(void *c, unsigned o) { (void)c; return reg[o]; }
static void wr(void *c, unsigned o, uint8_t v) { (void)c; wlog[log_n].off = o; wlog[log_n++].v = v; reg[o] = v; }
static const SatSmpcOps ops = { rd, wr, 0 };
#define OREG(n) reg[0x21 + (n) * 2]
static int index_of(unsigned off) { int i; for (i = 0; i < log_n; i++) if (wlog[i].off == off) return i; return -1; }

int main(void)
{
    static const SatPadMap map[] = { { SAT_PAD_RIGHT, 0x01 }, { SAT_PAD_LEFT, 0x02 }, { SAT_PAD_A, 0x20 }, { SAT_PAD_START, 0x100 } };
    /* idle SMPC (SF clear), a plain pad answered in port 1 and 2: the words are taken, then the next INTBACK is issued with SF before the command */
    OREG(0) = 0xf1; OREG(1) = 0x02; OREG(2) = 0xef; OREG(3) = 0xff; OREG(4) = 0xf1; OREG(5) = 0x02; OREG(6) = 0x7f; OREG(7) = 0xfb;
    sat_pad_tick_ops(&ops);
    CHECK_EQ(sat_pad_raw, 0xefff); CHECK_EQ(sat_pad_raw2, 0x7ffb);
    CHECK(index_of(0x63) >= 0 && index_of(0x1f) >= 0);
    CHECK(index_of(0x63) < index_of(0x1f));                       /* SF first, then COMREG */
    CHECK_EQ(wlog[index_of(0x1f)].v, 0x10);
    CHECK_EQ(wlog[log_n - 1].off, 0x1f);                           /* the command is the last write */
    /* SMPC busy: nothing is read or written */
    log_n = 0; reg[0x63] = 1; OREG(2) = 0; sat_pad_tick_ops(&ops); CHECK_EQ(log_n, 0); CHECK_EQ(sat_pad_raw, 0xefff);
    /* (SF is cleared by hand after each tick: the command that clears it is not simulated) unplugged port (status f0): idle word; a device that is not a plain pad: port 2 idle */
    reg[0x63] = 0; OREG(0) = 0xf0; sat_pad_tick_ops(&ops); reg[0x63] = 0; CHECK_EQ(sat_pad_raw, 0xffff);
    OREG(0) = 0xf1; OREG(1) = 0x02; OREG(2) = 0x0f; OREG(3) = 0xff; OREG(4) = 0xf1; OREG(5) = 0x34; sat_pad_tick_ops(&ops); reg[0x63] = 0; CHECK_EQ(sat_pad_raw, 0x0fff); CHECK_EQ(sat_pad_raw2, 0xffff);
    /* more data queued (SR bit 5): a break request, no command */
    log_n = 0; reg[0x61] = 0x20; sat_pad_tick_ops(&ops);
    CHECK_EQ(log_n, 2); CHECK_EQ(wlog[0].off, 0x01); CHECK_EQ(wlog[0].v, 0x40); CHECK_EQ(wlog[1].off, 0x63); CHECK_EQ(index_of(0x1f), -1);
    /* mapping: active low in, active low out */
    CHECK_EQ(sat_pad_map(0xffff, map, 4, 0x1ff, 1), 0x1ff);
    CHECK_EQ(sat_pad_map(0xffff & ~SAT_PAD_RIGHT & ~SAT_PAD_A, map, 4, 0x1ff, 1), 0x1ff & ~0x01 & ~0x20);
    CHECK_EQ(sat_pad_map(0xffff & ~SAT_PAD_START, map, 4, 0, 0), 0x100);
    PASS();
}
