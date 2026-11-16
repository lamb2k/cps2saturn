/* Host test: sat_lzdec decodes zlib raw deflate streams in place. argv: layout.bin out.bin
   layout.bin: u32 LE raw_total, nblk, tail, then nblk pairs (raw, compressed) u32 LE, then raw_total bytes of the destination as the loader leaves it
   (padded streams at the end). The decoded buffer is written to out.bin; exit code is lz_unit's result. */
#define LZ_HOST
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include "../../saturn/cd/sat_lzdec.h"

int main(int argc, char **argv)
{
    FILE *f; uint32_t hdr[3], *blk; lz8 *buf, *scr; LzCtx *z; int r; uint32_t k;
    if (argc < 3) return 2;
    f = fopen(argv[1], "rb");
    if (fread(hdr, 4, 3, f) != 3) return 2;
    blk = malloc(8u * hdr[1]);
    if (fread(blk, 4, 2 * hdr[1], f) != 2 * hdr[1]) return 2;
    buf = malloc(hdr[0] + 16); memset(buf, 0, hdr[0] + 16);
    if (fread(buf, 1, hdr[0], f) != hdr[0]) return 2;
    fclose(f);
    scr = malloc(hdr[2] + 16);
    z = malloc(sizeof *z);
    (void)k;
    r = lz_unit(z, buf, hdr[0], hdr[1], blk, hdr[2], scr);
    f = fopen(argv[2], "wb"); fwrite(buf, 1, hdr[0], f); fclose(f);
    if (r) fprintf(stderr, "lz_unit returned %d\n", r);
    return r == 0 ? 0 : 1;
}
