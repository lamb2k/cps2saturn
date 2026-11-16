/* Host test: sat_store reads rounds from a STORE.BIN built by tools/sector_store.py. argv: store.bin round out.bin
   Loads the round with an in-memory sector reader. Region destinations are offsets into a 1 MB buffer; the mark callback counts the regions loaded before it. */
#include <string.h>
#include "../../saturn/cd/sat_store.h"
#include "check.h"

static unsigned char *store_data; static long store_size; static int32_t pos;
static int io_seek(void *h, int32_t s) { (void)h; if ((long)s * 2048 > store_size) return 1; pos = s; return 0; }
static int io_read(void *h, int32_t n, void *d) { (void)h; if ((long)(pos + n) * 2048 > store_size) return 1; memcpy(d, store_data + (long)pos * 2048, (size_t)n * 2048); pos += n; return 0; }
static unsigned char *mem;
static int marks; static uint32_t mark_at_bytes;
static uint8_t *addr(uint32_t d, void *u) { (void)u; return mem + d; }
static void mark(void *u) { (void)u; marks++; mark_at_bytes = (uint32_t)(mem[0x40000] != 0); }

int main(int argc, char **argv)
{
    FILE *f; SatStore *st = malloc(sizeof *st); SatSectorIO io; SatRegionHooks hk; uint32_t head[512]; long r;
    if (argc < 4) return 2;
    f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); store_size = ftell(f); fseek(f, 0, SEEK_SET);
    store_data = malloc((size_t)store_size); if (fread(store_data, 1, (size_t)store_size, f) != (size_t)store_size) return 2; fclose(f);
    mem = calloc(1, 1 << 20);
    io.seek = io_seek; io.read = io_read; io.tick = 0; io.h = 0;
    CHECK_EQ(sat_store_open(st, &io), 0);
    hk.mark = mark; hk.addr = addr; hk.special = 0; hk.user = 0;
    if (strcmp(argv[2], "bad") == 0) {   /* round out of range, then a store with a damaged magic */
        CHECK_EQ(sat_store_load_round(st, 999, head, &hk), -0x100);
        store_data[0] = 0; CHECK(sat_store_open(st, &io) != 0); PASS();
    }
    r = sat_store_load_round(st, (uint32_t)atoi(argv[2]), head, &hk);
    printf("sectors %ld marks %d rounds %u\n", r, marks, sat_store_rounds(st));
    f = fopen(argv[3], "wb"); fwrite(mem, 1, 1 << 20, f); fclose(f);
    return r > 0 ? 0 : 1;
}
