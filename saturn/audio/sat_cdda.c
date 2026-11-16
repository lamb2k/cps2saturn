/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/audio/sat_audio.c (cd_command, cd_play_track, cd_pause, cd_service, cd_level, fade_tick, music_start's chain,
 * sat_audio_frame's CD part, sat_audio_resume_music). See sat_cdda.h. */
#include "sat_cdda.h"
#include "../include/sat_hw.h"

#define CD_FRAMES_PER_SECOND 75u

void sat_cdda_init(SatCdda *c, const SatCdHw *hw, unsigned fps)
{
    c->hw = hw; c->want = 0; c->level_now = 0xff; c->loop_next = 0; c->intro_left = 0;
    c->fade_level = 0xffffu; c->fade_dir = 0; c->fade_rate = 0; c->sent = 0; c->status = 0; c->fps = fps;
}

static void command(SatCdda *c, unsigned cr1, unsigned cr2, unsigned cr3, unsigned cr4)
{
    c->cmd[0] = (uint16_t)cr1; c->cmd[1] = (uint16_t)cr2; c->cmd[2] = (uint16_t)cr3; c->cmd[3] = (uint16_t)cr4;
    c->want = 1;
}

void sat_cdda_play_track(SatCdda *c, unsigned track, int repeat)
{
    command(c, 0x1000u, track << 8 | 1u, repeat ? 0x0f00u : 0u, track << 8 | 99u);   /* Play Disc, track and index */
}

void sat_cdda_pause(SatCdda *c)
{
    command(c, 0x11ffu, 0xffffu, 0, 0);
    c->loop_next = 0;
}

static void service(SatCdda *c)
{
    const SatCdHw *h = c->hw;
    if (!c->want || !(h->rd(h->ctx, SAT_CD_HIRQ_REG) & SAT_CD_HIRQ_CMOK)) return;   /* never wait: a busy CD block gets the command next frame */
    h->wr(h->ctx, SAT_CD_HIRQ_REG, (uint16_t)~SAT_CD_HIRQ_CMOK);
    h->wr(h->ctx, SAT_CD_CR1_REG, c->cmd[0]);
    h->wr(h->ctx, SAT_CD_CR2_REG, c->cmd[1]);
    h->wr(h->ctx, SAT_CD_CR3_REG, c->cmd[2]);
    h->wr(h->ctx, SAT_CD_CR4_REG, c->cmd[3]);   /* the write that starts the command */
    c->want = 0;
    c->sent++;
}

static void level(SatCdda *c, unsigned lv)
{
    if (lv == c->level_now) return;
    c->level_now = (uint8_t)lv;
    c->hw->input_level(c->hw->ctx, 0, (uint16_t)(lv << 5 | 0x1fu));   /* left input, hard left */
    c->hw->input_level(c->hw->ctx, 1, (uint16_t)(lv << 5 | 0x0fu));   /* right input, hard right */
}

void sat_cdda_music(SatCdda *c, unsigned intro_track, unsigned loop_track, uint32_t intro_cd_frames)
{
    c->fade_level = 0xffffu; c->fade_dir = 0;
    sat_cdda_play_track(c, intro_track ? intro_track : loop_track, !intro_track);
    c->loop_next = (uint8_t)(intro_track ? loop_track : 0);
    c->intro_left = intro_cd_frames * c->fps / CD_FRAMES_PER_SECOND;
}

void sat_cdda_fade(SatCdda *c, int dir, unsigned rate)
{
    if (!rate || c->fade_dir == dir) return;   /* no-op at rate 0 or when already going this way */
    if (!c->fade_dir) c->fade_level = dir > 0 ? 0 : 0xffffu;
    c->fade_dir = (int16_t)dir; c->fade_rate = (uint16_t)rate;
}

static void fade_tick(SatCdda *c)
{
    long next;
    if (!c->fade_dir) return;
    next = (long)c->fade_level + (c->fade_dir > 0 ? (long)c->fade_rate : -(long)c->fade_rate);
    if (next < 0 || next > 0xffffL) { c->fade_level = c->fade_dir > 0 ? 0xffffu : 0; c->fade_dir = 0; }
    else c->fade_level = (uint32_t)next;
}

void sat_cdda_frame(SatCdda *c)
{
    const SatCdHw *h = c->hw;
    fade_tick(c);
    level(c, c->fade_level >> 13);
    if (c->loop_next) {
        unsigned status = (h->rd(h->ctx, SAT_CD_CR1_REG) >> 8) & 0xfu;
        c->status = status;
        if (status == SAT_CD_STATUS_PLAY && c->intro_left) c->intro_left--;
        if (!c->intro_left) { sat_cdda_play_track(c, c->loop_next, 1); c->loop_next = 0; }
    }
    service(c);
}

void sat_cdda_after_load(SatCdda *c)
{
    c->want = 0; c->loop_next = 0;
    c->level_now = 0xff;
    level(c, c->fade_level >> 13);
}

#ifndef SAT_HOST
static uint16_t h_rd(void *x, unsigned r)
{
    (void)x;
    switch (r) { case 0: return SAT_CD_HIRQ; case 1: return SAT_CD_CR1; case 2: return SAT_CD_CR2; case 3: return SAT_CD_CR3; default: return SAT_CD_CR4; }
}
static void h_wr(void *x, unsigned r, uint16_t v)
{
    (void)x;
    switch (r) { case 0: SAT_CD_HIRQ = v; break; case 1: SAT_CD_CR1 = v; break; case 2: SAT_CD_CR2 = v; break; case 3: SAT_CD_CR3 = v; break; default: SAT_CD_CR4 = v; break; }
}
static void h_level(void *x, unsigned in, uint16_t v) { (void)x; SAT_SCSP_SLOT(16 + in, 0x16) = v; }
const SatCdHw sat_cdda_hw = { h_rd, h_wr, h_level, 0 };
#endif
