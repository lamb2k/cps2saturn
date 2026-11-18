/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Host test of the writer's wait in sat_v2g_name and sat_v2g_cram (saturn/gfx/sat_vdp2.c): a full queue waits only while a published picture is pending (publish mark ahead of the tail),
 * never when the tail is level with or ahead of the mark, also across the wrap of the 32 bit counters. The wait hook (SAT_HOST only) plays the master or counts the spins. */
#include <stdint.h>
#include <string.h>
#include "../../saturn/gfx/sat_vdp2.h"
#include "check.h"

static uint16_t regs[0x90]; static SatV2Latch L; static SatV2Gate G; static uint16_t cram[4096]; static uint8_t vram2[0x1000];
static uint32_t hook_n, apply_at, apply_serial;

static void hook(SatV2Gate *g)
{
    hook_n++;
    if (apply_at && hook_n == apply_at) sat_v2g_apply(g, apply_serial);   /* the master's V-blank apply of the picture that was published */
}

static void fresh(void)
{
    memset(vram2, 0, sizeof vram2); memset(cram, 0, sizeof cram); memset(regs, 0, sizeof regs);
    sat_v2l_init(&L, regs); sat_v2g_init(&G, &L, cram, vram2, 1);
    hook_n = 0; apply_at = 0; apply_serial = 0;
    sat_v2g_wait_hook = hook;
}
static void start_names(uint32_t at) { G.nq_head = G.nq_tail = G.nq_pub = at; }
static void start_cram(uint32_t at) { G.cq_head = G.cq_tail = G.cq_pub = at; }
static void fill_names(void) { unsigned i; for (i = 0; i < SAT_V2G_NAMEQ; i++) sat_v2g_name(&G, (i * 4) & 0xffc, 0x1000u + i); }
static void fill_cram(void) { unsigned i; for (i = 0; i < SAT_V2G_CRAMQ; i++) sat_v2g_cram(&G, i, 0x8000 | i); }

int main(void)
{
    CHECK(SAT_V2G_WAIT >= 50000u && SAT_V2G_WAIT <= 1000000u);   /* a few frames to well under a second at about 42 cycles a spin (see the header), not 20 million */

    /* names, the tail AHEAD of the publish mark (a direct drain moved it past a published picture): no wait at all */
    fresh(); start_names(0); fill_names();
    G.nq_pub = (uint32_t)-1024; CHECK_EQ(G.nq_head - G.nq_tail, SAT_V2G_NAMEQ);
    sat_v2g_name(&G, 0x20, 0xdead0001u);
    CHECK_EQ(hook_n, 0); CHECK_EQ(G.nq_direct, 1); CHECK_EQ(G.nq_tail, SAT_V2G_NAMEQ); CHECK_EQ(G.nq_head, SAT_V2G_NAMEQ + 1);
    CHECK_EQ(*(uint32_t *)(vram2 + 0x20), 0x1000u + 8);   /* the new entry (0xdead0001) is queued, not written; the queued ones were written out in order */
    CHECK_EQ(*(uint32_t *)(vram2 + 0xffc), 0x1000u + 1023);

    /* names, tail level with the mark: nothing pending, no wait (as before) */
    fresh(); start_names(0); fill_names(); G.nq_pub = G.nq_tail;
    sat_v2g_name(&G, 0x20, 1); CHECK_EQ(hook_n, 0); CHECK_EQ(G.nq_direct, 1);

    /* names, a published picture pending and the master applies it after 50 spins: the writer waits exactly that long, then queues without a direct write */
    fresh(); start_names(0); fill_names();
    sat_v2l_write(&L, 0x70, 0x0100); sat_v2g_publish(&G, 9); CHECK_EQ(G.nq_pub, SAT_V2G_NAMEQ);
    apply_at = 50; apply_serial = 9;
    sat_v2g_name(&G, 0x20, 0xdead0002u);
    CHECK_EQ(hook_n, 50); CHECK_EQ(G.nq_direct, 0); CHECK_EQ(G.nq_tail, SAT_V2G_NAMEQ); CHECK_EQ(G.nq_head, SAT_V2G_NAMEQ + 1);
    CHECK_EQ(*(uint32_t *)(vram2 + 0xffc), 0x1000u + 1023); CHECK_EQ(regs[0x70 / 2], 0x0100);

    /* names, pending but the master never comes (interrupts masked): the wait ends at the bound, SAT_V2G_WAIT - 1 spins, then the direct write */
    fresh(); start_names(0); fill_names(); sat_v2g_publish(&G, 9);
    sat_v2g_name(&G, 0x20, 3);
    CHECK_EQ(hook_n, SAT_V2G_WAIT - 1); CHECK_EQ(G.nq_direct, 1); CHECK_EQ(G.nq_tail, SAT_V2G_NAMEQ);

    /* names across the wrap of the counters: head wrapped past zero, pending (pub - tail > 0 although pub < tail as unsigned numbers) */
    fresh(); start_names(0xfffffe00u); fill_names();
    CHECK_EQ(G.nq_head, 0x200u); CHECK_EQ(G.nq_tail, 0xfffffe00u);
    sat_v2g_publish(&G, 9); CHECK_EQ(G.nq_pub, 0x200u);
    apply_at = 20; apply_serial = 9;
    sat_v2g_name(&G, 0x20, 4);
    CHECK_EQ(hook_n, 20); CHECK_EQ(G.nq_direct, 0); CHECK_EQ(G.nq_tail, 0x200u); CHECK_EQ(G.nq_head, 0x201u);
    CHECK_EQ(*(uint32_t *)(vram2 + 0xffc), 0x1000u + 1023);

    /* names across the wrap, tail ahead of the mark: the old test (tail != pub) waited here, the signed one does not */
    fresh(); start_names(0xfffffd00u); fill_names();
    CHECK_EQ(G.nq_head, 0x100u); G.nq_pub = G.nq_tail - 512u;   /* head - tail = 1024, pub - tail = -512 */
    sat_v2g_name(&G, 0x20, 5);
    CHECK_EQ(hook_n, 0); CHECK_EQ(G.nq_direct, 1); CHECK_EQ(G.nq_tail, 0x100u);

    /* colours: the same five cases */
    fresh(); start_cram(0); fill_cram(); G.cq_pub = (uint32_t)-1024;
    sat_v2g_cram(&G, 2000, 0x8abc);
    CHECK_EQ(hook_n, 0); CHECK_EQ(G.cq_direct, 1); CHECK_EQ(G.cq_tail, SAT_V2G_CRAMQ); CHECK_EQ(cram[1023], 0x8000 | 1023); CHECK_EQ(cram[2000], 0);

    fresh(); start_cram(0); fill_cram(); G.cq_pub = G.cq_tail;
    sat_v2g_cram(&G, 2000, 1); CHECK_EQ(hook_n, 0); CHECK_EQ(G.cq_direct, 1);

    fresh(); start_cram(0); fill_cram(); sat_v2g_publish(&G, 9); CHECK_EQ(G.cq_pub, SAT_V2G_CRAMQ);
    apply_at = 50; apply_serial = 9;
    sat_v2g_cram(&G, 2000, 2);
    CHECK_EQ(hook_n, 50); CHECK_EQ(G.cq_direct, 0); CHECK_EQ(G.cq_tail, SAT_V2G_CRAMQ); CHECK_EQ(cram[1023], 0x8000 | 1023);

    fresh(); start_cram(0); fill_cram(); sat_v2g_publish(&G, 9);
    sat_v2g_cram(&G, 2000, 3);
    CHECK_EQ(hook_n, SAT_V2G_WAIT - 1); CHECK_EQ(G.cq_direct, 1);

    fresh(); start_cram(0xfffffe00u); fill_cram();
    CHECK_EQ(G.cq_head, 0x200u); sat_v2g_publish(&G, 9); CHECK_EQ(G.cq_pub, 0x200u);
    apply_at = 20; apply_serial = 9;
    sat_v2g_cram(&G, 2000, 4);
    CHECK_EQ(hook_n, 20); CHECK_EQ(G.cq_direct, 0); CHECK_EQ(G.cq_tail, 0x200u); CHECK_EQ(cram[1023], 0x8000 | 1023);

    fresh(); start_cram(0xfffffd00u); fill_cram();
    CHECK_EQ(G.cq_head, 0x100u); G.cq_pub = G.cq_tail - 512u;
    sat_v2g_cram(&G, 2000, 5);
    CHECK_EQ(hook_n, 0); CHECK_EQ(G.cq_direct, 1); CHECK_EQ(G.cq_tail, 0x100u);

    sat_v2g_wait_hook = 0;
    PASS();
}
