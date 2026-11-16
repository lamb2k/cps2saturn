/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/audio/sat_audio.c (the SCSP driver core: smpc(), sat_audio_init's start sequence, start_sfx's slot
 * programming, channel_end, scsp_pan, the rate words).
 *
 * SCSP driver core: the SH-2 drives the SCSP directly. The sound CPU (a 68000 inside the SCSP) is parked on one instruction, so SCSP RAM
 * is sample space. There is no sequencer: each sound is one clip, rendered offline through the original driver, so its work is already in the sample.
 *
 *   sat_scsp_init()          SMPC sound off, park the 68000 (reset vectors and a branch-to-self in SCSP RAM), sound on, 512 KB RAM, master volume,
 *                            clear 32 slots. Up to three attempts: a first power-up on a console sometimes lost the SMPC command (SF busy), so each
 *                            wait is bounded and the result is read back from SCSP RAM.
 *   sat_scsp_write_ram()     samples into SCSP RAM, 16 bit big endian writes (the chip's RAM is word wide)
 *   sat_scsp_play()          one clip on one slot: PCM 8 or 16 bit, loop or one shot, level (TL), pan, rate
 *   sat_scsp_stop()          key off with immediate release
 *   sat_scsp_pan(), sat_scsp_rate_word()   pure helpers
 *
 * What a game supplies: the clip table (where each clip lives in SCSP RAM, its length, its rate), the policy (which slot, priorities, what a game
 * command means). The kit does not have a game's sound driver; sat_cdda.h has the CD audio half. */
#ifndef SAT_SCSP_H
#define SAT_SCSP_H
#include <stdint.h>

#define SAT_SCSP_CLIP_BASE 0x20u          /* RAM below it holds the parked 68000's vectors and idle loop */
#define SAT_SCSP_SLOTS 32
#define SAT_SCSP_PAN_CENTRE 0x10u
#define SAT_SCSP_PAN_MAX 0x20u

/* Register access for host tests and the console alike. slot < 32, reg a byte offset inside the 0x20 byte slot block. */
typedef struct SatScspHw {
    void (*slot_wr)(void *ctx, unsigned slot, unsigned reg, uint16_t v);
    uint16_t (*slot_rd)(void *ctx, unsigned slot, unsigned reg);
    void (*ram_wr16)(void *ctx, uint32_t byte_offset, uint16_t v);
    uint16_t (*ram_rd16)(void *ctx, uint32_t byte_offset);
    void (*mixer_wr)(void *ctx, uint16_t v);
    void (*smpc_command)(void *ctx, unsigned command, int *timed_out);   /* waits for idle, breaks a queued INTBACK, issues, waits */
    void *ctx;
} SatScspHw;

typedef struct SatScspVoice {
    uint32_t start;        /* byte offset of the first sample in SCSP RAM (already including SAT_SCSP_CLIP_BASE) */
    uint32_t samples;      /* sample count; the hardware loop end register is 16 bits, so longer clips are clipped to 0xffff */
    uint16_t rate_word;    /* OCT and FNS field, from sat_scsp_rate_word() (SLOT register 0x10) */
    uint8_t tl;            /* total level, 0 loudest, 0xff silent */
    uint8_t pan;           /* 0..0x1f hardware pan (sat_scsp_pan) */
    uint8_t loop;          /* normal loop over the whole clip */
    uint8_t pcm16;         /* 16 bit samples (default 8) */
} SatScspVoice;

/* Returns the number of attempts used (1..3) and sets *status: bit 8 the RAM word read back and no SMPC wait ran out, bit 9 an SMPC wait ran out. */
int sat_scsp_init(const SatScspHw *hw, unsigned *status);
void sat_scsp_write_ram(const SatScspHw *hw, uint32_t byte_offset, const uint8_t *big_endian_data, uint32_t bytes);
void sat_scsp_clear_slots(const SatScspHw *hw);
void sat_scsp_play(const SatScspHw *hw, unsigned slot, const SatScspVoice *v);
void sat_scsp_stop(const SatScspHw *hw, unsigned slot);
void sat_scsp_set_pan(const SatScspHw *hw, unsigned slot, unsigned pan);
/* Hardware pan register value (bit 4 = left, 0..15 attenuation of the far side) for a game pan 0..0x20 with 0x10 the centre; mono forces the centre. */
unsigned sat_scsp_pan(unsigned game_pan, int stereo);
/* SCSP rate = 44100 * 2^OCT * (1 + FNS / 1024). Returns OCT in bits 14..11 and FNS in bits 9..0 for a sample rate in Hz (between 345 Hz and 88200 Hz). */
uint16_t sat_scsp_rate_word(uint32_t hz);

/* The console's register access (not available under SAT_HOST). */
extern const SatScspHw sat_scsp_hw;
#endif
