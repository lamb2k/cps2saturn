/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/audio/sat_audio.c (cd_command, cd_play_track, cd_pause, cd_service, cd_level, fade_tick, the intro to loop
 * chain in sat_audio_frame, sat_audio_resume_music).
 *
 * CD audio control through the CD block's command registers, and the music chain a game needs: an intro track that plays once, then a loop track
 * that repeats; fades; the SCSP input level the CD audio comes through. Never blocks: a command is queued and sent in sat_cdda_frame() when the
 * block is ready (HIRQ CMOK), otherwise next frame. A CD data read between rounds takes the drive: sat_cdda_after_load() forgets what was in flight
 * and the game replays the music it last asked for.
 *
 * The CD block starts a command when CR4 is written, so CR1 to CR3 go first and CR4 last, and CMOK is cleared before the write.
 * Play Disc as AvP sends it: CR1 = 0x1000, CR2 = (track << 8) | 1, CR3 = 0x0f00 for endless repeat (0 for once), CR4 = (track << 8) | 99. Pause: 0x11ff, 0xffff, 0, 0.
 * The CD audio reaches the output through SCSP slots 16 and 17 (the external inputs): register 0x16 of each holds the level (bits 5 to 7) and the pan,
 * left input hard left and right input hard right.
 *
 * What a game supplies: the track numbers and the intro length in CD frames (75 per second), and calls sat_cdda_frame() once per video frame. */
#ifndef SAT_CDDA_H
#define SAT_CDDA_H
#include <stdint.h>

typedef struct SatCdHw {
    uint16_t (*rd)(void *ctx, unsigned reg);              /* reg: 0 HIRQ, 1 CR1, 2 CR2, 3 CR3, 4 CR4 */
    void (*wr)(void *ctx, unsigned reg, uint16_t v);
    void (*input_level)(void *ctx, unsigned input, uint16_t v);   /* input 0 left, 1 right: SCSP slot 16 / 17 register 0x16 */
    void *ctx;
} SatCdHw;

enum { SAT_CD_HIRQ_REG = 0, SAT_CD_CR1_REG, SAT_CD_CR2_REG, SAT_CD_CR3_REG, SAT_CD_CR4_REG };
#define SAT_CD_HIRQ_CMOK 0x0001u
#define SAT_CD_STATUS_PLAY 3u

typedef struct SatCdda {
    const SatCdHw *hw;
    uint16_t cmd[4];
    uint8_t want;               /* a command is queued */
    uint8_t level_now;          /* last level written; 0xff forces a write */
    uint8_t loop_next;          /* loop track to start when the intro ends, 0 none */
    uint32_t intro_left;        /* video frames of intro still to play, counted once the drive reports play */
    uint32_t fade_level;        /* 16 bit, the top 3 bits go to the SCSP input */
    int16_t fade_dir;           /* +1 in, -1 out, 0 none */
    uint16_t fade_rate;         /* step per frame */
    uint32_t sent, status;      /* counters for a debugger */
    unsigned fps;               /* video frames per second the game calls sat_cdda_frame at (60) */
} SatCdda;

void sat_cdda_init(SatCdda *c, const SatCdHw *hw, unsigned fps);
void sat_cdda_play_track(SatCdda *c, unsigned track, int repeat);
void sat_cdda_pause(SatCdda *c);                                   /* also forgets a queued loop */
/* intro_track 0: play loop_track repeating. Otherwise play intro_track once, then loop_track repeating when the drive has played intro_cd_frames. */
void sat_cdda_music(SatCdda *c, unsigned intro_track, unsigned loop_track, uint32_t intro_cd_frames);
void sat_cdda_fade(SatCdda *c, int dir, unsigned rate);            /* dir +1 fade in, -1 fade out; rate 0 or the same direction as running: ignored */
void sat_cdda_frame(SatCdda *c);                                   /* once per video frame */
void sat_cdda_after_load(SatCdda *c);                              /* the drive is free again after a data load */
extern const SatCdHw sat_cdda_hw;                                  /* the console's registers (not under SAT_HOST) */
#endif
