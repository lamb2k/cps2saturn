/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta: the register addresses that saturn/rt/boot.c, saturn/rt/kernel.c, saturn/rt/pad.c,
 * saturn/gfx/sat_gfx.c and saturn/audio/sat_audio.c each spelled out, gathered in one header.
 *
 * Saturn hardware addresses and the few access helpers every saturn/ module shares. Nothing here belongs to a game.
 * Defining SAT_HOST (host tests) turns the cache-through alias into the identity, so the pure modules compile and run on a PC. */
#ifndef SAT_HW_H
#define SAT_HW_H
#include <stdint.h>

#ifdef SAT_HOST
#define SAT_UNC(addr) ((uintptr_t)(addr))
#else
#define SAT_UNC(addr) ((uintptr_t)(addr) | 0x20000000u)   /* cache-through alias: the same RAM seen with the SH-2 cache bypassed */
#endif
/* A 32 bit variable read or written through the alias, for words the two SH-2s share (hand-off counters, publish records). */
#define SAT_UNC32(v) (*(volatile uint32_t *)SAT_UNC(&(v)))
#define SAT_UNC16(v) (*(volatile uint16_t *)SAT_UNC(&(v)))
#define SAT_UNC8(v) (*(volatile uint8_t *)SAT_UNC(&(v)))
#define SAT_BARRIER() __asm__ volatile ("" : : : "memory")

/* Memory map (cached addresses unless the name says otherwise). */
#define SAT_LOW_RAM 0x00200000u        /* low work RAM, 1 MB */
#define SAT_HIGH_RAM 0x06000000u       /* high work RAM, 1 MB */
#define SAT_CART_RAM 0x02400000u       /* 4 MB RAM cartridge window, through the cache */
#define SAT_CART_RAM_UNC 0x22400000u
#define SAT_CART_ID ((volatile uint8_t *)0x24ffffffu)
#define SAT_CART_ENABLE ((volatile uint16_t *)0x257efffeu)   /* a word write of 1 enables the 4 MB cart (Sega's ST-TECH-47) */

/* Chips. The pointers are used by the modules that touch hardware directly. */
#define SAT_VDP1_VRAM ((volatile uint8_t *)0x25C00000u)
#define SAT_VDP1_REG(o) (*(volatile uint16_t *)(0x25D00000u + (o)))
#define SAT_VDP2_VRAM ((volatile uint8_t *)0x25E00000u)
#define SAT_VDP2_CRAM ((volatile uint8_t *)0x25F00000u)
#define SAT_VDP2_REG(o) (*(volatile uint16_t *)(0x25F80000u + (o)))
#define SAT_VDP2_TVSTAT 0x04
#define SAT_TVSTAT_VBLANK 0x0008u
#define SAT_VDP1_EDSR 0x10
#define SAT_EDSR_CEF 0x0002u           /* current frame end flag: VDP1 has finished plotting */
#define SAT_VDP1_TVMR 0x00
#define SAT_VDP1_FBCR 0x02
#define SAT_VDP1_PTMR 0x04
#define SAT_VDP1_EWDR 0x06
#define SAT_VDP1_EWLR 0x08
#define SAT_VDP1_EWRR 0x0a

/* SCU */
#define SAT_SCU32(o) (*(volatile uint32_t *)(0x25fe0000u + (o)))
#define SAT_SCU_IMS 0xa0               /* interrupt mask */
#define SAT_SCU_IST 0xa4               /* interrupt status */
#define SAT_SCU_ASR0 0xb0
#define SAT_SCU_ASR1 0xb4
#define SAT_SCU_AREF 0xb8
#define SAT_IRQ_VBLANK_IN 0x00000001u
/* Vector table entries (VBR at 0x06000000). */
#define SAT_VECTOR_BASE ((void (**)(void))0x06000000u)
#define SAT_VEC_VBLANK_IN 0x40
#define SAT_VEC_VBLANK_OUT 0x41
#define SAT_BIOS_SLAVE_ENTRY ((void (**)(void))0x06000250u)   /* where the BIOS sends a slave that was just switched on */
#define SAT_BIOS_SLAVE_STACK ((uint32_t *)0x060002acu)
#define SAT_BIOS_CHGSYSCK (*(void (**)(unsigned long))0x06000320u)   /* BIOS service: system clock change */

/* SH-2 on-chip: free running timer and cache control. The master and the slave each have their own. */
#define SAT_FRTH (*(volatile uint8_t *)0xfffffe12u)
#define SAT_FRTL (*(volatile uint8_t *)0xfffffe13u)
#define SAT_FTCSR (*(volatile uint8_t *)0xfffffe11u)
#define SAT_FTCR (*(volatile uint8_t *)0xfffffe16u)
#define SAT_CCR (*(volatile uint8_t *)0xfffffe92u)
#define SAT_SLAVE_WAKE (*(volatile uint16_t *)0x21000000u)   /* a write here pulls the slave's FRT input capture (the master-to-slave interrupt line) */
#define SAT_FTCSR_ICF 0x80u
static inline uint32_t sat_frt(void) { uint32_t h = SAT_FRTH; return (h << 8) | SAT_FRTL; }

/* SMPC */
#define SAT_SMPC(o) (*(volatile uint8_t *)(0x20100000u + (o)))
#define SAT_SMPC_IREG(n) SAT_SMPC(1 + (n) * 2)
#define SAT_SMPC_OREG(n) SAT_SMPC(0x21 + (n) * 2)
#define SAT_SMPC_COMREG SAT_SMPC(0x1f)
#define SAT_SMPC_SR SAT_SMPC(0x61)
#define SAT_SMPC_SF SAT_SMPC(0x63)
#define SAT_SMPC_SSHON 0x02
#define SAT_SMPC_SSHOFF 0x03
#define SAT_SMPC_SNDON 0x06
#define SAT_SMPC_SNDOFF 0x07
#define SAT_SMPC_INTBACK 0x10

/* SCSP and CD block */
#define SAT_SCSP_RAM ((volatile uint16_t *)0x25A00000u)
#define SAT_SCSP_RAM_BYTES 0x80000u
#define SAT_SCSP_SLOT(n, r) (*(volatile uint16_t *)(0x25B00000u + 0x20u * (n) + (r)))
#define SAT_SCSP_MIXER (*(volatile uint16_t *)0x25B00400u)
#define SAT_CD_HIRQ (*(volatile uint16_t *)0x25890008u)
#define SAT_CD_CR1 (*(volatile uint16_t *)0x25890018u)
#define SAT_CD_CR2 (*(volatile uint16_t *)0x2589001cu)
#define SAT_CD_CR3 (*(volatile uint16_t *)0x25890020u)
#define SAT_CD_CR4 (*(volatile uint16_t *)0x25890024u)
#endif
