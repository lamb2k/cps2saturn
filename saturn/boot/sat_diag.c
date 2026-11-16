/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/rt/boot.c (boot display, diag_* functions). The AvP-only parts (the post-credits reveal, the
 * access-cycle restore of saturn/gfx/sat_vdp2_cfg.h, the cycle diagnostic) stayed behind; the restore is the sat_diag_restore hook.
 * See sat_diag.h. */
#include "sat_diag.h"

#define V2R(o) SAT_VDP2_REG(o)
#define DIAG_TAB ((volatile unsigned short *)SAT_DIAG_TAB_ADDR)
#define DIAG_BANDS 22
#define DIAG_CODE_TOP 150

void (*sat_diag_restore)(void);
static unsigned short diag_col[DIAG_BANDS + 1];
static int diag_active, diag_seq, diag_cur, diag_ticks, diag_mark;
static unsigned diag_info_value;
static unsigned short diag_tvmd = 0x8000;

static void diag_fill(int a, int b, unsigned short c) { for (; a < b && a < SAT_DIAG_LINES; a++) DIAG_TAB[a] = c; }
static void diag_band(int k, unsigned short c) { if (k < DIAG_BANDS) diag_fill(1 + 6 * k, 6 + 6 * k, c); }
static void diag_code(unsigned v)
{
    int i;
    diag_info_value = v;
    for (i = 0; i < 16; i++) {
        diag_fill(DIAG_CODE_TOP + 4 * i, DIAG_CODE_TOP + 4 * i + 3, ((v >> (15 - i)) & 1) ? SAT_C_WHITE : SAT_C_BLACK);
        diag_fill(DIAG_CODE_TOP + 4 * i + 3, DIAG_CODE_TOP + 4 * i + 4, SAT_C_GREY);
    }
}
static void diag_render(unsigned code)
{
    int k;
    diag_fill(0, SAT_DIAG_LINES, SAT_C_GREY);
    for (k = 0; k < diag_seq && k < DIAG_BANDS; k++) diag_band(k, diag_col[k]);
    diag_code(code);
}
static void diag_wait(int frames)
{
    while (frames-- > 0) { while (V2R(SAT_VDP2_TVSTAT) & SAT_TVSTAT_VBLANK) ; while (!(V2R(SAT_VDP2_TVSTAT) & SAT_TVSTAT_VBLANK)) ; }
}

/* VDP2 registers are write-only, so none is saved: everything set here is rewritten by the runtime's own init. */
static void diag_takeover(void)
{
    int o;
    V2R(0x20) = 0;                                      /* BGON: no scroll screen */
    for (o = 0xf0; o <= 0xf6; o += 2) V2R(o) = 0;       /* PRISA-D: sprite priority 0 hides the BIOS logo's VDP1 sprites */
    V2R(0xec) = 0;                                      /* CCCTL */
    for (o = 0x10; o <= 0x1e; o += 2) V2R(o) = 0xffff;  /* VRAM cycle patterns: no layer reads VRAM, so none can show */
    V2R(0x00) = diag_tvmd;                              /* TVMD */
    V2R(0xac) = 0x8003;                                 /* BKTAU: per-line back screen, table in the last 512 bytes of VRAM */
    V2R(0xae) = 0xff00;                                 /* BKTAL */
}

void sat_diag_stage(unsigned colour)
{
    unsigned short c = (unsigned short)colour;
    if (!diag_active) return;
    if (!c) c = (diag_seq & 1) ? SAT_C_BLUE : SAT_C_GREEN;
    diag_cur = diag_seq;
    if (diag_seq < DIAG_BANDS) diag_col[diag_seq] = c;
    diag_band(diag_seq, c);
    diag_seq++;
    diag_ticks = 0; diag_mark = -1;
}
void sat_diag_tick(void)
{
    int top, k = diag_cur;
    if (!diag_active || k >= DIAG_BANDS) return;
    top = 1 + 6 * k;
    if (diag_mark >= 0) diag_fill(top + diag_mark, top + diag_mark + 2, diag_col[k]);
    diag_mark = 2 * (diag_ticks++ & 1);
    diag_fill(top + diag_mark, top + diag_mark + 2, SAT_C_WHITE);
}
void sat_diag_info(unsigned value) { if (diag_active) diag_code(value); }
void sat_diag_set_tvmd(unsigned tvmd_on) { diag_tvmd = (unsigned short)tvmd_on; }
void sat_diag_reinit(void)
{
    if (!diag_active) return;
    diag_takeover();
    diag_render(diag_info_value);
}

/* The call table's entries: same signature (a, b), so the runtime can reach them with sat_diag_call(). */
static void api_stage(unsigned long colour, unsigned long unused) { (void)unused; sat_diag_stage((unsigned)colour); }
static void api_reinit(unsigned long a, unsigned long b) { (void)a; (void)b; sat_diag_reinit(); }
static void api_done(unsigned long restore, unsigned long b)
{
    (void)b;
    if (restore) {
        if (sat_diag_restore) sat_diag_restore();
    }
    diag_active = 0; SAT_DIAG_API[SAT_DIAG_ACTIVE] = 0;
}
/* Marks between the bands and the stripes, a few lines each: the slave and the vblank handler can show how far a frame got without a debugger. */
static void api_mark(unsigned long which, unsigned long b)
{
    static const unsigned short col[11] = { 0, 0, 0, SAT_C_RED, SAT_C_GREEN, SAT_C_BLUE, SAT_C_CYAN, SAT_C_MAGENTA, SAT_C_YELLOW, SAT_C_WHITE, SAT_C_RED };
    (void)b;
    if (!diag_active) return;
    if (which == 1) diag_fill(134, 138, SAT_C_YELLOW);
    else if (which == 2) diag_fill(138, 142, SAT_C_WHITE);
    else if (which >= 3 && which < 10) diag_fill(140 + (int)which, 141 + (int)which, col[which]);
    else if (which == 10) diag_fill(132, 134, col[10]);
    else if (which >= 11 && which <= 18) {
        static const unsigned short c2[8] = { SAT_C_CYAN, SAT_C_MAGENTA, SAT_C_WHITE, SAT_C_GREEN, SAT_C_RED, SAT_C_YELLOW, SAT_C_CYAN, SAT_C_MAGENTA };
        int line = 128 - 2 * (int)(which - 11);
        diag_fill(line, line + 2, c2[which - 11]);
    }
}

void sat_diag_fail(unsigned code, unsigned short colour, unsigned extra)
{
    volatile unsigned long *d = (volatile unsigned long *)SAT_LOADER_DIAG_ADDR;
    d[0] = 0x53415444u; d[1] = code; d[2] = extra;   /* 'SATD' */
    if (!diag_active) for (;;) __asm__ volatile ("nop");
    __asm__ volatile ("ldc %0,sr" : : "r"(0xf0));
    if (diag_cur < DIAG_BANDS) diag_col[diag_cur] = colour;
    for (;;) {
        diag_fill(0, SAT_DIAG_LINES, colour);
        diag_wait(30);
        diag_render(code);
        diag_wait(60);
        if (extra) { diag_render(extra & 0xffffu); diag_wait(60); }
    }
}
static void api_fatal(unsigned long code, unsigned long detail)   /* the runtime's fatal handler, before its first picture */
{
    sat_diag_fail((unsigned)((code & 0xff) << 8 | (detail & 0xff)), code >= 0xf0 ? SAT_C_MAGENTA : SAT_C_RED, (unsigned)detail & 0xffffu);
}

void sat_diag_init(unsigned tvmd_on)
{
    diag_tvmd = (unsigned short)tvmd_on;
    diag_takeover();
    diag_fill(0, SAT_DIAG_LINES, SAT_C_GREY);
    diag_active = 1;
    SAT_DIAG_API[SAT_DIAG_STAGE] = (unsigned long)api_stage;
    SAT_DIAG_API[SAT_DIAG_FATAL] = (unsigned long)api_fatal;
    SAT_DIAG_API[SAT_DIAG_DONE] = (unsigned long)api_done;
    SAT_DIAG_API[SAT_DIAG_ACTIVE] = 1;
    SAT_DIAG_API[SAT_DIAG_REINIT] = (unsigned long)api_reinit;
    SAT_DIAG_API[SAT_DIAG_MARK] = (unsigned long)api_mark;
}

/* CPU exceptions (vectors 4, 6, 9, 10): each stub loads the stacked PC and its vector number and jumps to one C function. */
static void diag_exc_c(unsigned long pc, unsigned long vec) { sat_diag_fail(0xfe00u | (unsigned)vec, SAT_C_MAGENTA, (unsigned)pc & 0xffffu); }
void sat_diag_exc_tramp(unsigned long pc, unsigned long vec) { diag_exc_c(pc, vec); }
__asm__(".text\n.align 2\n"
        ".global _sat_diag_exc4\n_sat_diag_exc4: mov.l @r15,r4\n bra 9f\n mov #4,r5\n"
        ".global _sat_diag_exc6\n_sat_diag_exc6: mov.l @r15,r4\n bra 9f\n mov #6,r5\n"
        ".global _sat_diag_exc9\n_sat_diag_exc9: mov.l @r15,r4\n bra 9f\n mov #9,r5\n"
        ".global _sat_diag_exc10\n_sat_diag_exc10: mov.l @r15,r4\n mov #10,r5\n"
        "9: mov.l 1f,r0\n jmp @r0\n nop\n.align 2\n1: .long _sat_diag_exc_tramp\n");
extern void sat_diag_exc4(void), sat_diag_exc6(void), sat_diag_exc9(void), sat_diag_exc10(void);
void sat_diag_install_exceptions(void)
{
    volatile unsigned long **vt = (volatile unsigned long **)0x06000000u;
    vt[4] = (volatile unsigned long *)sat_diag_exc4; vt[6] = (volatile unsigned long *)sat_diag_exc6;
    vt[9] = (volatile unsigned long *)sat_diag_exc9; vt[10] = (volatile unsigned long *)sat_diag_exc10;
}
