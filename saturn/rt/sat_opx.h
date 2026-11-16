/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/rt/lift_target.h (OP8/OP16/OP32 over OPX.BIN): the flat form below, with alignment-safe reads.
 * The range store form (sat_opx_find) was written for the kit, for a game whose opcode view differs in too many places for a flat window.
 *
 * Opcode/data split of a CPS2 program ROM. The 68000 fetches opcodes and operands through the decrypted view, but the program also reads itself as
 * data (tables, jump targets) through the plain view, and the two differ where the game's decryption keeps them apart. A lifted game keeps the data
 * view as the cart's program image and a small OPX store of the ranges where the opcode view differs. Code that reads an opcode-view address calls
 * sat_opx8/16/32: a binary search over merged ranges, and a fall back to the data view where no range covers the address.
 *
 * OPX store (big endian, built by tools/opx_store.py):
 *   u32 n, then n entries of {u32 start, u32 length, u32 offset} sorted by start, ranges disjoint; offset counts from the store's first byte.
 *
 * What a game supplies: the store address and the data view address, with sat_opx_init() (or the host fixtures). No ROM bytes are in the kit. */
#ifndef SAT_OPX_H
#define SAT_OPX_H
#include <stdint.h>

typedef struct SatOpx {
    const uint8_t *store;     /* the OPX store in memory */
    const uint8_t *data_view; /* the data view image: address a is data_view[a] */
    uint32_t miss;            /* the last address no range covered (debugging) */
    uint32_t misses;
} SatOpx;

/* Flat form (AvP): OPX is a window of the opcode view the same size as the address range the lifted code reads, indexed by address. */
static inline uint32_t sat_opx_flat8(const uint8_t *opx, uint32_t a) { return opx[a]; }
static inline uint32_t sat_opx_flat16(const uint8_t *opx, uint32_t a) { return ((uint32_t)opx[a] << 8) | opx[a + 1]; }
static inline uint32_t sat_opx_flat32(const uint8_t *opx, uint32_t a) { return ((uint32_t)sat_opx_flat16(opx, a) << 16) | sat_opx_flat16(opx, a + 2); }

void sat_opx_init(SatOpx *x, const void *store, const void *data_view);
/* Pointer to the opcode view byte of address a, or NULL if no range covers it. */
const uint8_t *sat_opx_find(SatOpx *x, uint32_t a);
uint32_t sat_opx8(SatOpx *x, uint32_t a);
uint32_t sat_opx16(SatOpx *x, uint32_t a);
uint32_t sat_opx32(SatOpx *x, uint32_t a);
#endif
