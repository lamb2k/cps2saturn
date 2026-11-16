#!/usr/bin/env python3
"""CPS object list decoding and the VDP1 tile funnel, for CPS-2 and for CPS-1 / CPS-Dash. From the AvP tile funnel.

An object table entry is four big-endian words: x, y, code, attributes. Attributes on both formats: palette bank
bits 0-4, x flip bit 5, y flip bit 6, nx-1 bits 8-11, ny-1 bits 12-15. Multi-tile blocks step 16 px.

  cps2 (CPS-2):  end of list y >= 0x8000 or attributes >= 0xff00; code high bits (y & 0x6000) << 3; relative flag
                 (config); 10-bit coordinates; codes wrap inside a 16-code row only when not flipped.
  cps1 (CPS-1, CPS-Dash):  end of list attributes & 0xff00 == 0xff00; 16-bit code, mapped to the graphics ROM by the
                 game's mapper (cps_tiles.Mapper) before the block arithmetic, and a sprite whose code does not map
                 is not drawn; raw 9-bit coordinates, picture origin (64, 16); codes wrap in every flip.
                 The first entry is drawn on top.
The format follows the config's game.board (tools/boards.py); graphics.objects overrides the geometry.

usage:
  cps_objects.py decode OBJRAM.bin [--config C]            one frame's visible tiles, as text
  cps_objects.py funnel FRAMES.bin --stride N --offset M [--size S] [--solid KEYS.txt] [--config C]
      FRAMES.bin: fixed-size records, object RAM at byte M of each record of N bytes (a full golden's layout).
      Counts commands (visible, non-empty tiles), off-screen, empty, row runs and live palette banks per frame.
Counts only; no game data is printed. cps2_objects.py is the same tool under its old name.
"""
from __future__ import annotations

import argparse
import pathlib
import struct
import sys
from dataclasses import dataclass
from typing import Callable

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import boards  # noqa: E402
import cfg  # noqa: E402

DEFAULT = dict(format="cps2", entries=0x400, x_bias=64, y_bias=16, relative_flag=0x80, relative_dx=0x40,
               relative_dy=0x10, view_x=80, view_y=16, view_w=352, view_h=224)
CPS1_DEFAULT = dict(format="cps1", entries=0x100, view_x=64, view_y=16, view_w=384, view_h=224)


@dataclass
class Tile:
    sx: int
    sy: int
    code: int
    bank: int
    fx: int
    fy: int


def geometry(config: str | dict | None, board: str | None = None) -> dict:
    """The object format and geometry for a config (a path or a loaded dict), or for a board name."""
    c = cfg.load(config) if isinstance(config, (str, pathlib.Path)) else (config or {})
    board = board or boards.name(c)
    g = dict(DEFAULT if board == "cps2" else CPS1_DEFAULT)
    g.update(cfg.get(c, "graphics.objects", {}) or {})
    return g


def tiles(obj: bytes, g: dict = DEFAULT, mapper: Callable[[int], int | None] | None = None):
    """Yield (Tile, on_screen) for every tile of every object up to the end marker, in table order.
    mapper (cps1 only): sprite code -> graphics ROM tile, or None when the code does not map."""
    if g.get("format", "cps2") == "cps1":
        yield from _tiles_cps1(obj, g, mapper)
        return
    for i in range(g["entries"]):
        if i * 8 + 8 > len(obj):
            break
        xw, yw, cw, aw = struct.unpack_from(">4H", obj, i * 8)
        if yw >= 0x8000 or aw >= 0xFF00:
            break
        code = cw + ((yw & 0x6000) << 3)
        nx, ny = ((aw >> 8) & 15) + 1, ((aw >> 12) & 15) + 1
        fx, fy = (aw >> 5) & 1, (aw >> 6) & 1
        x, y = xw, yw
        if aw & g["relative_flag"]:
            x += g["relative_dx"]
            y += g["relative_dy"]
        x += g["x_bias"] - g["relative_dx"]
        y += g["y_bias"] - g["relative_dy"]
        for ty in range(ny):
            for tx in range(nx):
                sx = ((x + tx * 16) & 0x3FF) - g["view_x"]
                sy = ((y + ty * 16) & 0x3FF) - g["view_y"]
                if fx or fy:
                    t = code + (nx - 1 - tx if fx else tx) + 0x10 * (ny - 1 - ty if fy else ty)
                else:
                    t = (code & ~0xF) + ((code + tx) & 0xF) + 0x10 * ty
                on = -16 < sx < g["view_w"] and -16 < sy < g["view_h"]
                yield Tile(sx, sy, t, aw & 31, fx, fy), on


def _tiles_cps1(obj: bytes, g: dict, mapper):
    for i in range(min(g["entries"], len(obj) // 8)):
        xw, yw, code, aw = struct.unpack_from(">4H", obj, i * 8)
        if aw & 0xFF00 == 0xFF00:
            break
        if mapper is not None:
            code = mapper(code)
            if code is None:
                continue
        nx, ny = ((aw >> 8) & 15) + 1, ((aw >> 12) & 15) + 1
        fx, fy = (aw >> 5) & 1, (aw >> 6) & 1
        for ty in range(ny):
            row = ny - 1 - ty if fy else ty
            sy = ((yw + ty * 16) & 0x1FF) - g["view_y"]
            for tx in range(nx):
                col = nx - 1 - tx if fx else tx
                t = (code & ~0xF) + ((code + col) & 0xF) + 0x10 * row
                sx = ((xw + tx * 16) & 0x1FF) - g["view_x"]
                on = -16 < sx < g["view_w"] and -16 < sy < g["view_h"]
                yield Tile(sx, sy, t, aw & 31, fx, fy), on


def funnel(obj: bytes, solid: set[int] | None, g: dict = DEFAULT) -> dict:
    n = dict(tiles=0, offscreen=0, empty=0, commands=0, runs=0, banks=0)
    banks = set()
    last_row = None
    prev_x = None
    for t, on in tiles(obj, g):
        n["tiles"] += 1
        if not on:
            n["offscreen"] += 1
            continue
        if solid is not None and t.code not in solid:
            n["empty"] += 1
            continue
        n["commands"] += 1
        row = (t.sy, t.bank)
        if row != last_row or prev_x is None or t.sx != prev_x + 16:
            n["runs"] += 1
        last_row, prev_x = row, t.sx
        banks.add(t.bank)
    n["banks"] = len(banks)
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("decode")
    d.add_argument("objram", type=pathlib.Path)
    d.add_argument("--config")
    f = sub.add_parser("funnel")
    f.add_argument("frames", type=pathlib.Path)
    f.add_argument("--stride", type=lambda s: int(s, 0), required=True)
    f.add_argument("--offset", type=lambda s: int(s, 0), required=True)
    f.add_argument("--size", type=lambda s: int(s, 0), help="object table bytes (default: the format's whole table)")
    f.add_argument("--solid", type=pathlib.Path, help="hex sprite codes with a visible pen, one per line")
    f.add_argument("--config")
    a = ap.parse_args(argv)
    g = geometry(a.config)
    if a.cmd == "funnel" and a.size is None:
        a.size = g["entries"] * 8
    if a.cmd == "decode":
        for t, on in tiles(a.objram.read_bytes(), g):
            if on:
                print(f"{t.sx:4d} {t.sy:4d} bank {t.bank:2d} flip {t.fx}{t.fy} code {t.code:05x}")
        return 0
    solid = {int(l, 16) for l in a.solid.read_text().split()} if a.solid else None
    rows = []
    with open(a.frames, "rb") as fh:
        while True:
            r = fh.read(a.stride)
            if len(r) < a.stride:
                break
            rows.append(funnel(r[a.offset:a.offset + a.size], solid, g))
    if not rows:
        print("no frames")
        return 1
    print("frames", len(rows))
    for k in ("commands", "tiles", "offscreen", "empty", "runs", "banks"):
        v = sorted(x[k] for x in rows)
        print(k, "mean", round(sum(v) / len(v), 1), "p95", v[max(0, int(len(v) * 0.95) - 1)], "max", v[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
