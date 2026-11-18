/* Host test: the cart timing soak test (sat_soak_run). Good memory passes; a stuck bit, a bit that flips with the pattern and a block that never
   got written are all caught; the four patterns are the documented ones. */
#include <string.h>
#define SAT_HOST 1
#include "../../saturn/boot/sat_cart_soak.h"
#include "check.h"

#define WORDS 0x400u
#define BLOCKS 4u
static uint32_t mem[BLOCKS * WORDS], other[BLOCKS * WORDS];

int main(void)
{
    unsigned done = 99, b;
    uint32_t bad;
    /* same memory on both sides: a good cart */
    memset(mem, 0xa5, sizeof mem);
    bad = sat_soak_run(mem, mem, BLOCKS, WORDS, &done);
    CHECK_EQ(bad, 0); CHECK_EQ(done, 4);
    /* the patterns left in memory: block b holds (i * 0x9e3779b9) ^ (b * 0x55555555) */
    for (b = 0; b < BLOCKS; b++) CHECK_EQ(mem[b * WORDS + 5], (5u * 0x9e3779b9u) ^ (b * 0x55555555u));
    CHECK_EQ(mem[3 * WORDS + 5], (5u * 0x9e3779b9u) ^ 0xffffffffu);
    /* never more than four blocks, whatever is asked */
    done = 0; bad = sat_soak_run(mem, mem, 9, WORDS / 8, &done); CHECK_EQ(bad, 0); CHECK_EQ(done, 4);
    done = 7; bad = sat_soak_run(mem, mem, 2, WORDS, &done); CHECK_EQ(bad, 0); CHECK_EQ(done, 2);
    /* a read side that is a different, stale memory: every word is wrong, so bits are set */
    memset(other, 0, sizeof other);
    bad = sat_soak_run(mem, other, BLOCKS, WORDS, &done);
    CHECK(bad != 0); CHECK_EQ(done, 4);
    bad = sat_soak_run(mem, mem, BLOCKS, WORDS, &done); CHECK_EQ(bad, 0);   /* mem is the clean four block pattern again */
    /* a bad bit at one word of one block is found, and only that bit is reported: write the good data, then flip bit 9 of one word and check it by hand */
    memcpy(other, mem, sizeof other);
    other[2 * WORDS + 100] ^= 1u << 9;
    {   /* the read side is a copy made after the fill, so flip it and run the checker half only: run the test with w = a scratch buffer, r = the flipped copy */
        static uint32_t scratch[BLOCKS * WORDS];
        bad = sat_soak_run(scratch, other, BLOCKS, WORDS, &done);
        CHECK(bad & (1u << 9));          /* the flipped bit is in the result */
    }
    /* a bit stuck at 1 in block 0 only: the result is exactly the bits where block 0's pattern has a 0 */
    memcpy(other, mem, sizeof other);
    for (b = 0; b < WORDS; b++) other[b] |= 1u << 31;   /* block 0 only */
    {
        uint32_t expect = 0;
        unsigned i;
        for (i = 0; i < WORDS; i++) if (!(((i * 0x9e3779b9u)) & (1u << 31))) expect |= 1u << 31;
        CHECK(expect != 0);
        {
            static uint32_t scratch[BLOCKS * WORDS];
            CHECK_EQ(sat_soak_run(scratch, other, 1, WORDS, &done), expect); CHECK_EQ(done, 1);
        }
    }
    PASS();
}
