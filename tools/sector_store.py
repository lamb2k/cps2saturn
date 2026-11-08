#!/usr/bin/env python3
"""Shared sector store: every unique 2 KB sector of a set of round files once, in one disc file.

Round files repeat most of their sectors (shared tiles, sound sets, restores). Storing each unique sector once,
with a run table per round, shrank the AvP data track from 240,771 to 94,143 sectors, all rounds byte-identical.

Layout (big endian):
  sector 0     u32 'SST1', u32 rounds, then per round u32 first run, u32 run count (round i at byte 8 + 8 i)
  sectors 1..  runs, u32 each: store sector << 14 | sectors (1..16383), all rounds' runs back to back
  then         data sectors in first-use order, so each round's reads stay mostly sequential
Reading a round's runs in order gives its file back byte for byte; the loader walks that stream as it walks the file.

usage: sector_store.py DIR [--pattern 'R[0-9][0-9][0-9].BIN'] [--out STORE.BIN] [--keep KEEP_DIR | --remove]
  Round files must be numbered 0..n-1 in name order and a multiple of 2048 bytes.
  Writes the store, verifies every round, and only then moves (--keep) or deletes (--remove) the round files.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import shutil
import struct
import sys

SEC = 2048
MAGIC = 0x53535431
CMAX = (1 << 14) - 1


def build(files: list[bytes]) -> tuple[bytes, list[list[list[int]]]]:
    where: dict[bytes, int] = {}
    data: list[bytes] = []
    rounds = []
    for b in files:
        if len(b) % SEC:
            raise ValueError("round file not a multiple of 2048 bytes")
        runs: list[list[int]] = []
        for o in range(0, len(b), SEC):
            s = b[o:o + SEC]
            k = hashlib.blake2b(s, digest_size=16).digest()
            if k not in where:
                where[k] = len(data)
                data.append(s)
            q = where[k]
            if runs and runs[-1][0] + runs[-1][1] == q and runs[-1][1] < CMAX:
                runs[-1][1] += 1
            else:
                runs.append([q, 1])
        rounds.append(runs)
    nruns = sum(len(r) for r in rounds)
    if 8 + 8 * len(rounds) > SEC:
        raise ValueError("too many rounds for one header sector")
    run_secs = -(-nruns * 4 // SEC)
    base = 1 + run_secs
    if base + len(data) >= 1 << 18:
        raise ValueError("store too large for 18-bit sector numbers")
    head = struct.pack(">II", MAGIC, len(rounds))
    tab, first = bytearray(), 0
    for r in rounds:
        head += struct.pack(">II", first, len(r))
        first += len(r)
        for q, n in r:
            tab += struct.pack(">I", (base + q) << 14 | n)
    out = head + bytes(SEC - len(head)) + tab + bytes(run_secs * SEC - len(tab)) + b"".join(data)
    return out, rounds


def rebuild(store: bytes, i: int) -> bytes:
    magic, n = struct.unpack_from(">II", store)
    if magic != MAGIC or i >= n:
        raise ValueError("bad store or round index")
    first, cnt = struct.unpack_from(">II", store, 8 + 8 * i)
    out = bytearray()
    for j in range(first, first + cnt):
        w = struct.unpack_from(">I", store, SEC + 4 * j)[0]
        q, c = w >> 14, w & CMAX
        out += store[q * SEC:(q + c) * SEC]
    return bytes(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", type=pathlib.Path)
    ap.add_argument("--pattern", default="R[0-9][0-9][0-9].BIN")
    ap.add_argument("--out", default="STORE.BIN")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--keep", type=pathlib.Path)
    g.add_argument("--remove", action="store_true")
    a = ap.parse_args(argv)
    names = sorted(a.dir.glob(a.pattern))
    nums = [int(re.sub(r"\D", "", p.stem) or -1) for p in names]
    if not names or nums != list(range(len(nums))):
        sys.exit("round files missing or not numbered 0..n-1")
    files = [p.read_bytes() for p in names]
    store, rounds = build(files)
    bad = [i for i, b in enumerate(files) if rebuild(store, i) != b]
    if bad:
        sys.exit(f"rounds differ after rebuild: {bad}")
    (a.dir / a.out).write_bytes(store)
    if a.keep:
        a.keep.mkdir(parents=True, exist_ok=True)
        for p in names:
            shutil.move(str(p), str(a.keep / p.name))
    elif a.remove:
        for p in names:
            p.unlink()
    old = sum(len(b) for b in files) // SEC
    print(f"sector store: rounds {len(files)}, round sectors {old}, store sectors {len(store) // SEC}, "
          f"runs {sum(len(r) for r in rounds)}, max runs {max(len(r) for r in rounds)}, identical {len(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
