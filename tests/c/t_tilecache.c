/* Host test: sat_tilecache. Scenario test with a fake pack: key k has the 8 byte payload {k, k, ...}; keys >= 1000 are blank, keys >= 2000 missing. */
#include <string.h>
#include "../../saturn/gfx/sat_tilecache.h"
#include "check.h"

#define CAP 8
static uint8_t vram[CAP * 8]; static uint8_t pay[8];
static SatTcSlot slots[CAP]; static uint16_t head[16]; static uint32_t neg[16];
static int fetches, uploads;
static int fetch(void *c, uint32_t k, const uint8_t **p) { (void)c; fetches++; if (k >= 2000) return SAT_TC_MISSING; if (k >= 1000) return SAT_TC_BLANK; memset(pay, (int)k, 8); *p = pay; return SAT_TC_PAYLOAD; }
static void up(uint8_t *d, const uint8_t *s, uint32_t n) { uploads++; memcpy(d, s, n); }

int main(void)
{
    SatTileCache c; uint16_t a, b, s[CAP + 2]; unsigned i;
    sat_tc_init(&c, vram, 8, CAP, 1, slots, head, 16, neg, 16, fetch, up, 0);
    sat_tc_frame(&c);
    a = sat_tc_get(&c, 5); CHECK(a != SAT_TC_NOSLOT); CHECK(a >= 1);                /* slot 0 is reserved */
    CHECK_EQ(vram[a * 8], 5); CHECK_EQ(uploads, 1);
    b = sat_tc_get(&c, 5); CHECK_EQ(a, b); CHECK_EQ(uploads, 1);                    /* memo hit */
    sat_tc_get(&c, 6); b = sat_tc_get(&c, 5); CHECK_EQ(a, b); CHECK_EQ(uploads, 2); /* chain hit after the memo moved on */
    CHECK_EQ(c.used, 2);
    /* blank and missing: one fetch each, then the negative cache answers */
    fetches = 0;
    CHECK_EQ(sat_tc_get(&c, 1001), SAT_TC_NOSLOT); CHECK_EQ(sat_tc_get(&c, 2002), SAT_TC_NOSLOT);
    CHECK_EQ(fetches, 2); sat_tc_frame(&c);
    CHECK_EQ(sat_tc_get(&c, 1001), SAT_TC_NOSLOT); CHECK_EQ(sat_tc_get(&c, 2002), SAT_TC_NOSLOT);
    CHECK_EQ(fetches, 2); CHECK_EQ(c.missing, 1);
    sat_tc_forget_negative(&c); sat_tc_frame(&c); sat_tc_get(&c, 1001); CHECK_EQ(fetches, 3);
    /* capacity: 7 usable slots, the 8th distinct key of one frame is refused and nothing in use is evicted */
    sat_tc_frame(&c);
    for (i = 0; i < 7; i++) { s[i] = sat_tc_get(&c, 100 + i); CHECK(s[i] != SAT_TC_NOSLOT); }
    CHECK_EQ(sat_tc_get(&c, 200), SAT_TC_NOSLOT); CHECK_EQ(c.refused, 1);
    for (i = 0; i < 7; i++) CHECK_EQ(vram[s[i] * 8], 100 + i);
    /* next frame: old keys evictable, the previous plot's slots are protected when asked */
    sat_tc_commit(&c); c.protect_prev = 1; sat_tc_frame(&c);
    CHECK_EQ(sat_tc_get(&c, 300), SAT_TC_NOSLOT);                                    /* every slot belongs to the plot in flight */
    c.protect_prev = 0; CHECK(sat_tc_get(&c, 300) == SAT_TC_NOSLOT);                 /* memoised refusal for this frame */
    sat_tc_frame(&c); a = sat_tc_get(&c, 300); CHECK(a != SAT_TC_NOSLOT);            /* now it may take one */
    /* abandon: slots this build touched go back to the last submitted plot's stamp */
    sat_tc_commit(&c); sat_tc_frame(&c); a = sat_tc_get(&c, 301); CHECK(a != SAT_TC_NOSLOT);
    CHECK_EQ(slots[a].stamp, c.stamp); sat_tc_abandon(&c); CHECK_EQ(slots[a].stamp, c.prev_stamp);
    /* a key evicted and asked for again uploads again and finds its own slot, with the chain intact */
    sat_tc_frame(&c);
    for (i = 0; i < 7; i++) CHECK(sat_tc_get(&c, 400 + i) != SAT_TC_NOSLOT);
    uploads = 0; sat_tc_frame(&c);
    for (i = 0; i < 7; i++) { a = sat_tc_get(&c, 400 + i); CHECK(a != SAT_TC_NOSLOT); CHECK_EQ(vram[a * 8], (400 + i) & 0xff); }
    CHECK_EQ(uploads, 0);
    PASS();
}
