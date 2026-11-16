#!/usr/bin/env python3
"""Builds and reads the OPX range store that saturn/rt/sat_opx.c looks up (CPS2 opcode view ranges).

Written for the kit. Format (big endian): u32 n, then n entries {u32 start, u32 length, u32 offset}, sorted by start, disjoint; offset counts from the
store's first byte; the bytes follow the table. Ranges whose opcode view bytes equal the data view are not worth storing: --diff keeps only the stretches
where two views differ.

usage: opx_store.py build OUT --data DATA_VIEW.bin --ops OPCODE_VIEW.bin [--pad 16] [--base 0]
       opx_store.py show STORE
Both inputs are your own files; the store is derived data: keep it out of git.
"""
import argparse
import struct
import sys


def diff_ranges(data, ops, pad=16, base=0):
    """Merged (start, length) ranges where the two views differ, each widened by pad bytes on both sides (words stay inside)."""
    n = min(len(data), len(ops))
    out = []
    i = 0
    while i < n:
        if data[i] == ops[i]:
            i += 1
            continue
        j = i
        while j < n and data[j] != ops[j]:
            j += 1
        out.append([max(0, i - pad), min(n, j + pad)])
        i = j
    merged = []
    for a, b in out:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [(a + base, b - a) for a, b in merged]


def build(ranges, ops, base=0):
    """ranges: [(start, length)] in address space; ops: bytes of the opcode view indexed by (address - base)."""
    rs = sorted(ranges)
    for (a, n), (b, _) in zip(rs, rs[1:]):
        if a + n > b:
            raise ValueError("ranges overlap")
    head = struct.pack(">I", len(rs))
    off = 4 + 12 * len(rs)
    table, body = b"", b""
    for a, n in rs:
        table += struct.pack(">III", a, n, off + len(body))
        body += ops[a - base:a - base + n]
    return head + table + body


def read(store):
    n = struct.unpack_from(">I", store)[0]
    return [struct.unpack_from(">III", store, 4 + 12 * i) for i in range(n)]


def lookup(store, a):
    """Python model of sat_opx_find: the stored byte for address a, or None."""
    lo, hi = 0, struct.unpack_from(">I", store)[0] - 1
    while lo <= hi:
        m = (lo + hi) >> 1
        st, n, off = struct.unpack_from(">III", store, 4 + 12 * m)
        if a < st:
            hi = m - 1
        elif a >= st + n:
            lo = m + 1
        else:
            return store[off + (a - st)]
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("out")
    b.add_argument("--data", required=True)
    b.add_argument("--ops", required=True)
    b.add_argument("--pad", type=int, default=16)
    b.add_argument("--base", type=lambda s: int(s, 0), default=0)
    s = sub.add_parser("show")
    s.add_argument("store")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "build":
            data, ops = open(a.data, "rb").read(), open(a.ops, "rb").read()
            rs = diff_ranges(data, ops, a.pad, a.base)
            open(a.out, "wb").write(build(rs, ops, a.base))
            print(f"{len(rs)} ranges, {sum(n for _, n in rs)} bytes")
        else:
            for st, n, off in read(open(a.store, "rb").read()):
                print(f"{st:08x} {n:6d} @{off}")
    except (OSError, ValueError) as e:
        print(f"opx_store: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
