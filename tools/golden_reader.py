#!/usr/bin/env python3
"""Read goldens written by tools/mame/golden.lua (full or delta), and diff two of them.

usage:
  golden_reader.py info GOLDEN --config C [--delta]
  golden_reader.py show GOLDEN FIRST LAST --config C [--delta] [--lo HEX --hi HEX]
  golden_reader.py diff A B --config C [--delta]        first record where work RAM or object RAM differ
Output holds RAM values: print to the terminal, do not commit.
"""
from __future__ import annotations

import argparse
import pathlib
import struct
import sys
from typing import Iterator

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cfg  # noqa: E402

HEAD = 8 + 64


def records(path: pathlib.Path, work_size: int, obj_size: int, delta: bool) -> Iterator[tuple[int, tuple, bytes]]:
    """Yield (irq number, 16 registers, full RAM image work+object) per record. Delta records are applied."""
    total = (work_size + obj_size) // 4
    cur = bytearray(total * 4)
    with open(path, "rb") as f:
        while True:
            h = f.read(HEAD)
            if len(h) < HEAD:
                return
            if h[:4] != b"VBLK":
                raise ValueError("bad record marker")
            n = struct.unpack_from(">I", h, 4)[0]
            regs = struct.unpack_from(">16I", h, 8)
            if delta:
                runs = struct.unpack(">I", f.read(4))[0]
                for _ in range(runs):
                    b, w = struct.unpack(">HH", f.read(4))
                    cur[b * 4:(b + w) * 4] = f.read(w * 4)
                yield n, regs, bytes(cur)
            else:
                yield n, regs, f.read(work_size + obj_size)


def sizes(c: dict) -> tuple[int, int, int]:
    return cfg.get(c, "ram.work_base"), cfg.get(c, "ram.work_size"), cfg.get(c, "ram.object_size")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["info", "show", "diff"])
    ap.add_argument("args", nargs="+")
    ap.add_argument("--config", required=True)
    ap.add_argument("--delta", action="store_true")
    ap.add_argument("--lo", type=lambda s: int(s, 16))
    ap.add_argument("--hi", type=lambda s: int(s, 16))
    a = ap.parse_args(argv)
    c = cfg.load(a.config)
    base, ws, os_ = sizes(c)
    if a.cmd == "info":
        n = last = 0
        for irq, _, _ in records(pathlib.Path(a.args[0]), ws, os_, a.delta):
            n, last = n + 1, irq
        print("records", n, "last irq", last)
    elif a.cmd == "show":
        first, last = int(a.args[1]), int(a.args[2])
        lo, hi = a.lo or base, a.hi or base + ws
        prev = None
        for irq, r, img in records(pathlib.Path(a.args[0]), ws, os_, a.delta):
            if irq > last:
                break
            if irq >= first:
                ch = []
                if prev is not None:
                    for o in range(max(0, lo - base), min(ws, hi - base), 4):
                        if img[o:o + 4] != prev[o:o + 4]:
                            ch.append(f"{base + o:x}={img[o:o + 4].hex()}")
                print(irq, f"pc {r[0]:x} d0 {r[1]:x} a0 {r[9]:x} a4 {r[13]:x} a6 {r[15]:x}", " ".join(ch))
            prev = img
    else:
        ra = records(pathlib.Path(a.args[0]), ws, os_, a.delta)
        rb = records(pathlib.Path(a.args[1]), ws, os_, a.delta)
        count = 0
        for (ia, _, ma), (ib, _, mb) in zip(ra, rb):
            if ma != mb:
                o = next(i for i in range(0, len(ma), 4) if ma[i:i + 4] != mb[i:i + 4])
                where = f"work {base + o:x}" if o < ws else f"object +{o - ws:x}"
                print(f"first difference at record {count} (irq {ia}/{ib}): {where}")
                return 1
            count += 1
        print(f"identical over {count} records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
