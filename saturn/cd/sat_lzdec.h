/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Moved from avpsaturn v0.1.0-beta, saturn/rt/lzdec.h (lane loading, 2026-11-12). Changes: fixed width types, static functions marked unused,
 * comments re-pointed at the kit. The slow path symbol decode (lz_sym, the loop over code lengths) is the canonical method of puff.c by Mark Adler (zlib licence, permissive; credited here and in NOTICE.md). Nothing is taken from a GPL source.
 */
/* sat_lzdec.h: raw deflate (RFC 1951) decoder for the loader (lane loading, 2026-11-12, SAT_LOAD_LZ). No malloc, no libc; table driven (fast table for codes up to LZ_LB / LZ_DB bits,
   the canonical slow path of puff.c for longer ones). Shared by a loader (SH-2, big endian) and the host test (tests/test_saturn_host.py, built with -DLZ_HOST): the same text is what is verified.
   Streams are produced by zlib (raw, wbits -15, level 9); the kit's test builds them with Python's zlib. The input may be read up to 4 bytes beyond a stream's last byte (the bit buffer refills a byte at a time):
   callers keep 4 readable bytes after the last stream.
   lz_unit() decodes a list of independent streams one after another into one destination buffer IN PLACE: the compressed streams (each padded to whole sectors) were read into the end of the
   buffer, the output grows from its start; the last `tail` bytes of the buffer are copied to a scratch area first and the decoder reads them from there (so the output may pass over them). */
#ifndef SAT_LZDEC_H
#define SAT_LZDEC_H
#include <stdint.h>
#define LZ_LB 10u
#define LZ_DB 7u
#ifdef _MSC_VER
#define LZ_AL4
#else
#define LZ_AL4 __attribute__((aligned(4)))
#endif
typedef uint8_t lz8; typedef uint16_t lz16; typedef uint32_t lz32;
#define LZ_UNUSED __attribute__((unused))
typedef struct {
    const lz8 *src, *swp, *scr; lz32 bits; int nbits; lz8 *dst, *dend;   /* when src reaches swp it continues at scr (the tail kept in scratch) */
    lz16 lcnt[16], lsym[288], dcnt[16], dsym[32], ltab[1u << LZ_LB], dtab[1u << LZ_DB];
} LzCtx;
static const lz16 lz_lbase[29] LZ_AL4 = { 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258 };
static const lz8 lz_lext[29] = { 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0 };
static const lz16 lz_dbase[30] LZ_AL4 = { 1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577 };
static const lz8 lz_dext[30] = { 0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13 };
static const lz8 lz_clorder[19] = { 16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15 };

/* 16 bits of the input per refill, always from an even address (every stream starts on a sector and the tail copy on an even offset): one aligned halfword read and a byte swap on the SH-2 (big endian) instead of
   two byte reads. */
#if defined(__sh__) && !defined(LZ_HOST)
#define LZ_RD16(p) ((lz32)__builtin_bswap16(*(const lz16 *)(p)))
#else
#define LZ_RD16(p) ((lz32)(((const lz8 *)(p))[0] | ((lz32)((const lz8 *)(p))[1] << 8)))
#endif
static LZ_UNUSED void lz_need(LzCtx *z, int n) { while (z->nbits < n) { if (z->src == z->swp) z->src = z->scr; z->bits |= LZ_RD16(z->src) << z->nbits; z->src += 2; z->nbits += 16; } }

/* canonical table from code lengths: cnt[len], sym sorted by (length, symbol), tab[bit reversed code] = sym << 4 | len for codes of up to tb bits. */
static LZ_UNUSED void lz_build(lz16 *cnt, lz16 *sym, lz16 *tab, unsigned tb, const lz8 *len, int n)
{
    lz16 offs[17]; lz32 next[17], code = 0; int i, l;
    for (l = 0; l < 16; l++) cnt[l] = 0;
    for (i = 0; i < n; i++) cnt[len[i]]++;
    cnt[0] = 0;
    for (l = 0; l < (1 << tb); l++) tab[l] = 0;
    offs[1] = 0; for (l = 1; l < 15; l++) offs[l + 1] = (lz16)(offs[l] + cnt[l]);
    for (i = 0; i < n; i++) if (len[i]) sym[offs[len[i]]++] = (lz16)i;
    for (l = 1; l < 16; l++) { code = (code + (l > 1 ? cnt[l - 1] : 0)) << 1; next[l] = code; }
    if (!tb) return;
    for (i = 0; i < n; i++) {
        l = len[i];
        if (l && l <= (int)tb) {
            lz32 c = next[l]++, r = 0; int k; unsigned idx;
            for (k = 0; k < l; k++) { r = (r << 1) | (c & 1); c >>= 1; }
            for (idx = (unsigned)r; idx < (1u << tb); idx += 1u << l) tab[idx] = (lz16)(i << 4 | l);
        } else if (l) next[l]++;
    }
}
static LZ_UNUSED int lz_sym(LzCtx *z, const lz16 *tab, unsigned tb, const lz16 *cnt, const lz16 *sym)
{
    int code = 0, first = 0, index = 0, l;
    lz_need(z, 15);
    if (tb) {
        lz16 e = tab[z->bits & ((1u << tb) - 1)];
        if (e) { l = e & 15; z->bits >>= l; z->nbits -= l; return e >> 4; }
    }
    for (l = 1; l < 16; l++) {
        int c;
        code |= (int)(z->bits & 1); z->bits >>= 1; z->nbits--;
        c = cnt[l];
        if (code - c < first) return sym[index + (code - first)];
        index += c; first += c; first <<= 1; code <<= 1;
    }
    return -1;
}
/* Shifts by a variable count: the SH-2 has only fixed shifts (1, 2, 8, 16), so a variable shift is a libgcc loop. Right shifts go through a 32x32 -> 64 bit multiply (dmulu.l, high word) and
   left shifts through a multiply by a power of two, both table driven. Other targets (the host test) use the plain operators. */
#ifdef __sh__
static const lz32 lz_p32[32] = { 0, 0x80000000ul, 0x40000000ul, 0x20000000ul, 0x10000000ul, 0x8000000ul, 0x4000000ul, 0x2000000ul, 0x1000000ul, 0x800000ul, 0x400000ul, 0x200000ul, 0x100000ul, 0x80000ul, 0x40000ul, 0x20000ul,
    0x10000ul, 0x8000ul, 0x4000ul, 0x2000ul, 0x1000ul, 0x800ul, 0x400ul, 0x200ul, 0x100ul, 0x80ul, 0x40ul, 0x20ul, 0x10ul, 8ul, 4ul, 2ul };
static const lz32 lz_p2[32] = { 1ul, 2ul, 4ul, 8ul, 0x10ul, 0x20ul, 0x40ul, 0x80ul, 0x100ul, 0x200ul, 0x400ul, 0x800ul, 0x1000ul, 0x2000ul, 0x4000ul, 0x8000ul, 0x10000ul, 0x20000ul, 0x40000ul, 0x80000ul, 0x100000ul,
    0x200000ul, 0x400000ul, 0x800000ul, 0x1000000ul, 0x2000000ul, 0x4000000ul, 0x8000000ul, 0x10000000ul, 0x20000000ul, 0x40000000ul, 0x80000000ul };
#define LZ_SHR(x, n) ((n) ? (lz32)(((unsigned long long)(x) * lz_p32[n]) >> 32) : (x))
#define LZ_SHR1(x, n) ((lz32)(((unsigned long long)(x) * lz_p32[n]) >> 32))   /* n >= 1 (a table entry's length) */
#define LZ_SHLB(b, n) ((lz32)(b) * lz_p2[n])
#else
#define LZ_SHR(x, n) ((x) >> (n))
#define LZ_SHR1(x, n) ((x) >> (n))
#define LZ_SHLB(b, n) ((lz32)(b) << (n))
#endif
static const lz16 lz_mask[17] = { 0, 1, 3, 7, 15, 31, 63, 127, 255, 511, 1023, 2047, 4095, 8191, 16383, 32767, 65535 };

/* one deflate stream into dst (up to dend); returns bytes written or -1. The bit buffer lives in locals in the symbol loop. */
static LZ_UNUSED long lz_inflate(LzCtx *z, const lz8 *src, lz8 *dst, lz8 *dend)
{
    int last; lz8 *d0 = dst;
    const lz8 *swp = z->swp, *scr = z->scr;
    lz32 bb = 0; int nb = 0; const lz8 *sp = src; lz8 *d = dst;
#define LZ_NEED(n) while (nb < (n)) { if (sp == swp) sp = scr; bb |= LZ_SHLB(LZ_RD16(sp), nb); sp += 2; nb += 16; }
#define LZ_BITS(n, v) { LZ_NEED(n); (v) = (int)(bb & lz_mask[n]); bb = LZ_SHR(bb, n); nb -= (n); }
#define LZ_SAVE() { z->src = sp; z->bits = bb; z->nbits = nb; }
#define LZ_LOAD() { sp = z->src; bb = z->bits; nb = z->nbits; }
    do {
        int type;
        LZ_BITS(1, last); LZ_BITS(2, type);
        if (type == 0) {
            int len, nlen;
            bb = LZ_SHR(bb, nb & 7); nb -= nb & 7;
            LZ_BITS(16, len); LZ_BITS(16, nlen); (void)nlen;
            if (d + len > dend) return -1;
            while (len--) { int v; LZ_BITS(8, v); *d++ = (lz8)v; }
        } else if (type == 1 || type == 2) {
            lz8 lens[320]; int i, nlen, ndist;
            if (type == 1) {
                for (i = 0; i < 144; i++) lens[i] = 8;
                for (; i < 256; i++) lens[i] = 9;
                for (; i < 280; i++) lens[i] = 7;
                for (; i < 288; i++) lens[i] = 8;
                for (i = 0; i < 30; i++) lens[288 + i] = 5;
                nlen = 288; ndist = 30;
            } else {
                lz8 cl[19]; lz16 ccnt[16], csym[19], ctab[1]; int hc;
                LZ_BITS(5, nlen); nlen += 257; LZ_BITS(5, ndist); ndist += 1; LZ_BITS(4, hc); hc += 4;
                if (nlen > 286 || ndist > 30) return -1;
                { int k; for (k = 0; k < 19; k++) cl[k] = 0; for (k = 0; k < hc; k++) { int v; LZ_BITS(3, v); cl[lz_clorder[k]] = (lz8)v; } }
                lz_build(ccnt, csym, ctab, 0, cl, 19);
                for (i = 0; i < nlen + ndist; ) {
                    int s, rep, v = 0;
                    LZ_SAVE(); s = lz_sym(z, ctab, 0, ccnt, csym); LZ_LOAD();
                    if (s < 0) return -1;
                    if (s < 16) { lens[i++] = (lz8)s; continue; }
                    if (s == 16) { if (!i) return -1; v = lens[i - 1]; LZ_BITS(2, rep); rep += 3; }
                    else if (s == 17) { LZ_BITS(3, rep); rep += 3; } else { LZ_BITS(7, rep); rep += 11; }
                    if (i + rep > nlen + ndist) return -1;
                    while (rep--) lens[i++] = (lz8)v;
                }
                { int k; for (k = ndist - 1; k >= 0; k--) lens[288 + k] = lens[nlen + k]; }   /* distance lengths up to a fixed place (nlen <= 286 < 288: moving upward from the end is safe) */
            }
            lz_build(z->lcnt, z->lsym, z->ltab, LZ_LB, lens, nlen);
            lz_build(z->dcnt, z->dsym, z->dtab, LZ_DB, lens + 288, ndist);
            for (;;) {
                int s; lz16 e;
                /* one refill test per symbol: nb <= 16 -> 16 more bits (nb <= 32); then nb >= 17 covers any code (15 bits). Literals do not test the output end: it is checked here, at the refill, and at every match. */
                if (nb <= 16) { if (sp == swp) sp = scr; bb |= LZ_SHLB(LZ_RD16(sp), nb); sp += 2; nb += 16; if (d > dend) return -1; }
                e = z->ltab[bb & ((1u << LZ_LB) - 1)];
                if (e) {
                    int l = e & 15; bb = LZ_SHR1(bb, l); nb -= l; s = e >> 4;
                    if (s < 256) { *d++ = (lz8)s; continue; }
                } else {
                    LZ_SAVE(); s = lz_sym(z, z->ltab, LZ_LB, z->lcnt, z->lsym); LZ_LOAD();
                    if (s < 0) return -1;
                    if (s < 256) { if (d >= dend) return -1; *d++ = (lz8)s; continue; }
                }
                if (s == 256) break;
                {
                    int len, dist, x; const lz8 *p;
                    s -= 257; if (s >= 29) return -1;
                    x = lz_lext[s]; len = lz_lbase[s]; if (x) { int v; LZ_BITS(x, v); len += v; }
                    LZ_NEED(15);
                    e = z->dtab[bb & ((1u << LZ_DB) - 1)];
                    if (e) { int l = e & 15; bb = LZ_SHR(bb, l); nb -= l; s = e >> 4; }
                    else { LZ_SAVE(); s = lz_sym(z, z->dtab, LZ_DB, z->dcnt, z->dsym); LZ_LOAD(); }
                    if (s < 0 || s >= 30) return -1;
                    x = lz_dext[s]; dist = lz_dbase[s]; if (x) { int v; LZ_BITS(x, v); dist += v; }
                    if (d - d0 < dist || d + len > dend) return -1;
                    p = d - dist;
                    if (len >= 4 && !(((uintptr_t)d | (uintptr_t)p) & 1)) { while (len >= 2) { *(lz16 *)d = *(const lz16 *)p; d += 2; p += 2; len -= 2; } }   /* both even: halfword moves (dist >= 2: reads stay behind the writes) */
                    while (len >= 4) { d[0] = p[0]; d[1] = p[1]; d[2] = p[2]; d[3] = p[3]; d += 4; p += 4; len -= 4; }   /* bytes in order: a distance below 4 overlaps its own output */
                    while (len--) *d++ = *p++;
                }
            }
        } else return -1;
    } while (!last);
    z->dst = d;
    return (long)(d - d0);
}
/* Decode nblk streams in place. dest: buffer of raw_total bytes. blk[2k] = raw bytes of stream k, blk[2k+1] = its compressed bytes; stream k lies at base + (sum of the padded sizes before it), where
   base = dest + raw_total - (sum of all padded sizes) and a padded size is the compressed size rounded up to 2048. The last `tail` bytes of the buffer are copied to `scratch` (capacity tail + 8)
   once the streams have all arrived; the decoder switches to the copy when its input reaches them. The unit can be run in steps while the streams are still arriving (a loader's stream function): a stream
   may be decoded as soon as its padded bytes are in, and whose output does not reach the tail before the tail has been copied. */
typedef struct { lz8 *dest; lz32 raw_total, nblk, tail, k, off, out, padded; const lz32 *blk; lz8 *scratch, *base, *swp; } LzUnit;
static LZ_UNUSED void lz_unit_begin(LzCtx *z, LzUnit *u, lz8 *dest, lz32 raw_total, lz32 nblk, const lz32 *blk, lz32 tail, lz8 *scratch)
{
    lz32 k;
    u->dest = dest; u->raw_total = raw_total; u->nblk = nblk; u->blk = blk; u->tail = tail; u->scratch = scratch;
    u->k = 0; u->off = 0; u->out = 0; u->padded = 0;
    for (k = 0; k < nblk; k++) u->padded += (blk[2 * k + 1] + 2047ul) & ~2047ul;
    u->base = dest + raw_total - u->padded; u->swp = dest + raw_total - tail;
    z->swp = (const lz8 *)0; z->scr = scratch;   /* until the tail has been copied the decoder never reads it */
}
static LZ_UNUSED void lz_unit_tailcopy(LzCtx *z, LzUnit *u)
{
    lz32 q;
    z->scr = u->scratch; z->swp = u->tail ? u->swp : (const lz8 *)0;
    for (q = 0; q < u->tail; q++) u->scratch[q] = u->swp[q];
    for (q = 0; q < 8; q++) u->scratch[u->tail + q] = 0;
}
/* the next stream: 1 = decoded, 0 = it must wait (its padded bytes have not all arrived, `arrived` = number of bytes from base that have; or its output would reach the tail before the tail is copied), < 0 = error */
static LZ_UNUSED int lz_unit_step(LzCtx *z, LzUnit *u, lz32 arrived, int tail_done)
{
    lz32 pk, pad_k; const lz8 *s; long n;
    if (u->k >= u->nblk) return 0;
    pk = u->blk[2 * u->k + 1]; pad_k = (pk + 2047ul) & ~2047ul;
    if (u->off + pad_k > arrived) return 0;
    if (!tail_done && u->tail && u->dest + u->out + u->blk[2 * u->k] > u->swp) return 0;
    s = u->base + u->off;
    if (tail_done && u->tail && s >= u->swp) s = u->scratch + (s - u->swp);
    n = lz_inflate(z, s, u->dest + u->out, u->dest + u->raw_total);
    if (n != (long)u->blk[2 * u->k]) return -1 - (int)u->k;
    u->out += u->blk[2 * u->k]; u->off += pad_k; u->k++;
    return 1;
}
/* all at once (the streams are all in): 0 or a negative code */
static LZ_UNUSED int lz_unit(LzCtx *z, lz8 *dest, lz32 raw_total, lz32 nblk, const lz32 *blk, lz32 tail, lz8 *scratch)
{
    LzUnit u; int r;
    lz_unit_begin(z, &u, dest, raw_total, nblk, blk, tail, scratch);
    lz_unit_tailcopy(z, &u);
    while ((r = lz_unit_step(z, &u, u.padded, 1)) > 0) ;
    if (r < 0) return r;
    return (u.k == u.nblk && u.out == raw_total) ? 0 : -100;
}
#endif
