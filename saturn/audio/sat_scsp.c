/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/audio/sat_audio.c (smpc, sat_audio_init, start_sfx, channel_end, scsp_pan). See sat_scsp.h. */
#include "sat_scsp.h"
#include "../include/sat_hw.h"

#define KEY_EXECUTE 0x1000u
#define KEY_ON 0x0800u
#define PCM8 0x0010u
#define LOOP_NORMAL 0x0020u
#define PCM_16_BITS 0x0000u
#define R_PLAY 0x00
#define R_SAH 0x02
#define R_LSA 0x04
#define R_LEA 0x06
#define R_EG1 0x08
#define R_EG2 0x0a
#define R_TL 0x0c
#define R_MIX 0x0e
#define R_OCT 0x10
#define R_PAN 0x16

unsigned sat_scsp_pan(unsigned pan, int stereo)
{
    if (!stereo) pan = SAT_SCSP_PAN_CENTRE;
    if (pan < SAT_SCSP_PAN_CENTRE) { pan = SAT_SCSP_PAN_CENTRE - pan; return 0x10u | (pan > 15 ? 15 : pan); }
    pan -= SAT_SCSP_PAN_CENTRE;
    return pan > 15 ? 15 : pan;
}

uint16_t sat_scsp_rate_word(uint32_t hz)
{
    /* Find the octave that puts hz / (44100 * 2^oct) in [1, 2), then the fraction in 1/1024ths. 32 bit arithmetic is enough for 345 Hz to 88200 Hz. */
    uint32_t base = 44100u, h = hz, fns;
    int oct = 0;
    if (!hz) return 0;
    while (h >= 2 * base && oct < 7) { base *= 2; oct++; }
    while (h < base && oct > -8) { h *= 2; oct--; }
    fns = (h * 1024u + base / 2) / base - 1024u;
    if (fns > 1023u) { fns = 0; oct++; }
    return (uint16_t)(((uint32_t)(oct & 0xf) << 11) | fns);
}

void sat_scsp_clear_slots(const SatScspHw *hw)
{
    unsigned n, i;
    for (n = 0; n < SAT_SCSP_SLOTS; n++) for (i = 0; i < 0x18; i += 2) hw->slot_wr(hw->ctx, n, i, 0);
    hw->slot_wr(hw->ctx, 0, R_PLAY, KEY_EXECUTE);
}

int sat_scsp_init(const SatScspHw *hw, unsigned *status)
{
    unsigned n, st = 0;
    for (n = 0; n < 3; n++) {
        int to_off = 0, to_on = 0;
        st = (st & 0xff00u) | (n + 1);                                             /* bit 9 stays set once any wait ran out (information) */
        hw->smpc_command(hw->ctx, SAT_SMPC_SNDOFF, &to_off);
        hw->ram_wr16(hw->ctx, 0, 0x0007u); hw->ram_wr16(hw->ctx, 2, 0xfffcu);     /* 68000 reset: initial stack pointer */
        hw->ram_wr16(hw->ctx, 4, 0x0000u); hw->ram_wr16(hw->ctx, 6, 0x0010u);     /* initial pc */
        hw->ram_wr16(hw->ctx, 0x10, 0x60feu);                                     /* bra.s to itself */
        hw->smpc_command(hw->ctx, SAT_SMPC_SNDON, &to_on);
        hw->mixer_wr(hw->ctx, 0x0200u | 0xfu);                                    /* 512 KB RAM, master volume full */
        if (to_off || to_on) st |= 0x200u;
        /* AvP kept the sticky bit in its break test, so a first timeout always cost all three attempts; here an attempt that is clean ends the loop. */
        if (hw->ram_rd16(hw->ctx, 0x10) == 0x60feu && !to_off && !to_on) { st |= 0x100u; n++; break; }
    }
    sat_scsp_clear_slots(hw);
    if (status) *status = st;
    return (int)(n > 3 ? 3 : n);
}

void sat_scsp_write_ram(const SatScspHw *hw, uint32_t off, const uint8_t *d, uint32_t bytes)
{
    uint32_t i;
    for (i = 0; i + 1 < bytes; i += 2) hw->ram_wr16(hw->ctx, off + i, (uint16_t)(d[i] << 8 | d[i + 1]));
}

void sat_scsp_set_pan(const SatScspHw *hw, unsigned slot, unsigned pan)
{
    hw->slot_wr(hw->ctx, slot, R_PAN, (uint16_t)(7u << 13 | (pan & 0x1fu) << 8));
}

void sat_scsp_play(const SatScspHw *hw, unsigned s, const SatScspVoice *v)
{
    void *c = hw->ctx;
    uint16_t play = (uint16_t)((v->pcm16 ? PCM_16_BITS : PCM8) | (v->loop ? LOOP_NORMAL : 0) | (v->start >> 16));
    hw->slot_wr(c, s, R_PLAY, play);
    hw->slot_wr(c, s, R_SAH, (uint16_t)v->start);
    hw->slot_wr(c, s, R_LSA, 0);
    hw->slot_wr(c, s, R_LEA, (uint16_t)(v->samples > 0xffffu ? 0xffffu : v->samples));
    hw->slot_wr(c, s, R_EG1, 0x001fu | 1u << 5);                 /* attack at once, then hold */
    hw->slot_wr(c, s, R_EG2, 0x001fu);                           /* release at once */
    hw->slot_wr(c, s, R_TL, v->tl);
    hw->slot_wr(c, s, R_MIX, 0);
    hw->slot_wr(c, s, R_OCT, v->rate_word);
    hw->slot_wr(c, s, 0x12, 0);
    hw->slot_wr(c, s, 0x14, 0);
    sat_scsp_set_pan(hw, s, v->pan);
    hw->slot_wr(c, s, R_PLAY, (uint16_t)(play | KEY_ON | KEY_EXECUTE));
}

void sat_scsp_stop(const SatScspHw *hw, unsigned s)
{
    hw->slot_wr(hw->ctx, s, R_PLAY, (uint16_t)((hw->slot_rd(hw->ctx, s, R_PLAY) & ~KEY_ON) | KEY_EXECUTE));
}

#ifndef SAT_HOST
static void h_slot_wr(void *c, unsigned n, unsigned r, uint16_t v) { (void)c; SAT_SCSP_SLOT(n, r) = v; }
static uint16_t h_slot_rd(void *c, unsigned n, unsigned r) { (void)c; return SAT_SCSP_SLOT(n, r); }
static void h_ram_wr16(void *c, uint32_t o, uint16_t v) { (void)c; SAT_SCSP_RAM[o >> 1] = v; }
static uint16_t h_ram_rd16(void *c, uint32_t o) { (void)c; return SAT_SCSP_RAM[o >> 1]; }
static void h_mixer(void *c, uint16_t v) { (void)c; SAT_SCSP_MIXER = v; }
/* The SMPC wait for idle first: the BIOS polls it every frame and a command written while it is busy is lost. A peripheral INTBACK that still has
   data queued makes the SMPC ignore other commands until it is broken. */
static void h_smpc(void *c, unsigned command, int *timed_out)
{
    int wait;
    (void)c;
    for (wait = 0; wait < 400000 && (SAT_SMPC_SF & 1); wait++) ;
    if (wait >= 400000) *timed_out = 1;
    if (SAT_SMPC_SR & 0x20) {
        SAT_SMPC_IREG(0) = 0x40; SAT_SMPC_SF = 1; SAT_SMPC_COMREG = SAT_SMPC_INTBACK;
        for (wait = 0; wait < 400000 && (SAT_SMPC_SF & 1); wait++) ;
    }
    SAT_SMPC_SF = 1;
    SAT_SMPC_COMREG = (uint8_t)command;
    for (wait = 0; wait < 400000 && (SAT_SMPC_SF & 1); wait++) ;
    if (wait >= 400000) *timed_out = 1;
}
const SatScspHw sat_scsp_hw = { h_slot_wr, h_slot_rd, h_ram_wr16, h_ram_rd16, h_mixer, h_smpc, 0 };
#endif
