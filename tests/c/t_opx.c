/* Host test: sat_opx. argv: store.bin data.bin addr... ; prints, for each address, the 8, 16 and 32 bit values as hex (find results use the store, misses the data view). */
#include <stdio.h>
#include <stdlib.h>
#include "../../saturn/rt/sat_opx.h"

static unsigned char *slurp(const char *n, long *sz)
{
    FILE *f = fopen(n, "rb"); unsigned char *b; fseek(f, 0, SEEK_END); *sz = ftell(f); fseek(f, 0, SEEK_SET);
    b = malloc((size_t)*sz + 8); if (fread(b, 1, (size_t)*sz, f) != (size_t)*sz) exit(2); fclose(f); return b;
}
int main(int argc, char **argv)
{
    long a, b; unsigned char *store = slurp(argv[1], &a), *data = slurp(argv[2], &b); SatOpx x; int i;
    sat_opx_init(&x, store, data);
    for (i = 3; i < argc; i++) {
        unsigned long ad = strtoul(argv[i], 0, 0);
        printf("%lx %02x %04x %08x %d\n", ad, sat_opx8(&x, ad), sat_opx16(&x, ad), sat_opx32(&x, ad), sat_opx_find(&x, ad) != 0);
    }
    printf("flat %04x\n", sat_opx_flat16(data, 2));
    return 0;
}
