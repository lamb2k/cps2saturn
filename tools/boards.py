#!/usr/bin/env python3
"""What differs between Capcom boards, for the tools that care. The board comes from the config's game.board.

  cps2     CPS-2 (the default when game.board is missing)
  cps1     CPS-1: YM2151 + OKI6295 sound, DIP switches
  cpsdash  CPS-Dash (QSound CPS-1, also called CPS-1.5): CPS-1 video, QSound, EEPROM

Facts are from MAME 0.289's address maps and video code (see docs/design/cps1-dash-boards.md). No MAME code here.
Any value can be overridden in the config: video.cps_a, ram.object_table, ram.object_size.

usage: boards.py CONFIG     prints the board and the values the tools will use
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cfg  # noqa: E402

_CPS1_VIDEO = dict(
    opcode_space=False,     # MAME gives the 68000 no decrypted opcode view
    object_table="register",  # in GFX RAM, at CPS-A register 0x00 x 256
    cps_a=0x800100,
    gfx_ram=0x900000,
    object_align=0x800,
    object_size=0x800,
)

BOARDS = {
    "cps2": dict(opcode_space=True, object_table="fixed", cps_a=0x804100, gfx_ram=0x900000, object_align=0x800,
                 object_size=0x2000),
    "cps1": dict(_CPS1_VIDEO),
    "cpsdash": dict(_CPS1_VIDEO),
}


def name(c: dict) -> str:
    b = cfg.get(c, "game.board") or "cps2"
    if b not in BOARDS:
        sys.exit(f"game.board {b!r}: expected one of {', '.join(BOARDS)}")
    return b


def value(c: dict, key: str):
    return BOARDS[name(c)][key]


def cps_a(c: dict) -> int:
    return cfg.get(c, "video.cps_a") or value(c, "cps_a")


def object_table(c: dict) -> str:
    t = cfg.get(c, "ram.object_table") or value(c, "object_table")
    if t not in ("fixed", "register"):
        sys.exit(f"ram.object_table {t!r}: expected fixed or register")
    return t


def object_size(c: dict) -> int:
    return cfg.get(c, "ram.object_size") or value(c, "object_size")


if __name__ == "__main__":
    c = cfg.load(sys.argv[1])
    print("board", name(c))
    print("object_table", object_table(c), "size", hex(object_size(c)))
    if object_table(c) == "register":
        print("cps_a", hex(cps_a(c)), "gfx_ram", hex(value(c, "gfx_ram")), "align", hex(value(c, "object_align")))
    else:
        print("object_base", hex(cfg.get(c, "ram.object_base")))
    print("opcode_space", value(c, "opcode_space"))
