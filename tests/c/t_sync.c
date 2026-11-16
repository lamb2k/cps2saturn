/* Host test: sat_sync's hand-off counters. */
#define SAT_HOST 1
#include "../../saturn/rt/sat_sync.h"
#include "check.h"

static int order[4], n;
static void begin(void) { order[n++] = 1; }
static void layers(void) { order[n++] = 3; }
int main(void)
{
    volatile uint32_t flag = 0;
    CHECK(sat_sync_slave_idle());
    CHECK(sat_sync_try_handoff(begin, layers));                    /* begin, count the picture, then the layer half */
    CHECK_EQ(sat_gfx_handed, 1); CHECK_EQ(order[0], 1); CHECK_EQ(order[1], 3);
    CHECK(!sat_sync_slave_idle());
    n = 0; CHECK(!sat_sync_try_handoff(begin, layers)); CHECK_EQ(n, 0); CHECK_EQ(sat_gfx_skips, 1);   /* a slave still drawing skips the picture */
    sat_gfx_done = 1; CHECK(sat_sync_try_handoff(begin, 0)); CHECK_EQ(sat_gfx_handed, 2);
    sat_sync_snapshot_clear(&flag); CHECK_EQ(flag, 0); sat_sync_snapshot_set(&flag); sat_sync_snapshot_wait(&flag); CHECK_EQ(flag, 1);
    PASS();
}
