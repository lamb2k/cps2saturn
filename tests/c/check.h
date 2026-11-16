/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Tiny assertion helper for the host tests of saturn/. A failed CHECK prints the line and exits 1; a test prints PASS and exits 0. */
#ifndef CHECK_H
#define CHECK_H
#include <stdio.h>
#include <stdlib.h>
#define CHECK(c) do { if (!(c)) { printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); exit(1); } } while (0)
#define CHECK_EQ(a, b) do { long long a_ = (long long)(a), b_ = (long long)(b); if (a_ != b_) { printf("FAIL %s:%d: %s == %s (%lld vs %lld)\n", __FILE__, __LINE__, #a, #b, a_, b_); exit(1); } } while (0)
#define PASS() do { printf("PASS\n"); return 0; } while (0)
#endif
