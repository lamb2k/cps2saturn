/* Host test: sat_layer. A 64 x 64 big endian name map in the game's column order (row_bits 5: 32 row pages). */
#include <string.h>
#include "../../saturn/gfx/sat_layer.h"
#include "check.h"

static uint8_t map[64 * 64 * 4];
static uint32_t at(uint32_t c, uint32_t r) { return ((c & 63) << 5) + (r & 31) + (((r & 63) >> 5) << 11); }   /* word index: column, row inside the page, page row */
static void put(uint32_t c, uint32_t r, uint32_t v) { uint8_t *p = map + at(c, r) * 4; p[0] = (uint8_t)(v >> 24); p[1] = (uint8_t)(v >> 16); p[2] = (uint8_t)(v >> 8); p[3] = (uint8_t)v; }

int main(void)
{
    uint32_t dest[6 * 5], sum, sum2, dirty = 0, r, c; SatLayerMemo m = { 0, 0 };
    for (c = 0; c < 64; c++) for (r = 0; r < 64; r++) put(c, r, c * 1000 + r);
    /* the visible window wraps at 64 in both directions: columns 62..66, rows 61..66 */
    sum = sat_layer_snapshot(dest, map, 62, 61, 6, 5, 5, 0, 0xdeadbeef, 0);
    for (r = 0; r < 6; r++) for (c = 0; c < 5; c++) CHECK_EQ(dest[r * 5 + c], ((62 + c) & 63) * 1000 + ((61 + r) & 63));
    /* unchanged: same sum, and the copy is skipped (the destination keeps whatever it held) */
    dest[0] = 7; sum2 = sat_layer_snapshot(dest, map, 62, 61, 6, 5, 5, 0, sum, 0); CHECK_EQ(sum2, sum); CHECK_EQ(dest[0], 7);
    /* a changed word moves the sum and is copied */
    put(63, 63, 4242); sum2 = sat_layer_snapshot(dest, map, 62, 61, 6, 5, 5, 0, sum, 0); CHECK(sum2 != sum); CHECK_EQ(dest[2 * 5 + 1], 4242u);
    /* dirty rows: only the row that changed is flagged */
    put(63, 63, 5555); sum = sat_layer_snapshot(dest, map, 62, 61, 6, 5, 5, 0, sum2, &dirty); CHECK_EQ(dirty, 1u << 2); CHECK_EQ(dest[2 * 5 + 1], 5555u);
    /* the mix is order sensitive: swapping two words changes the sum */
    put(62, 61, 1); put(63, 61, 2); sum = sat_layer_snapshot(dest, map, 62, 61, 6, 5, 5, 0, 0, 0);
    put(62, 61, 2); put(63, 61, 1); sum2 = sat_layer_snapshot(dest, map, 62, 61, 6, 5, 5, 0, 0, 0); CHECK(sum != sum2);
    /* memo */
    CHECK_EQ(sat_layer_needs_draw(&m, 5), 1); CHECK_EQ(sat_layer_needs_draw(&m, 5), 0); CHECK_EQ(sat_layer_needs_draw(&m, 6), 1);
    sat_layer_invalidate(&m); CHECK_EQ(sat_layer_needs_draw(&m, 6), 1);
    PASS();
}
