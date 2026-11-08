#!/usr/bin/env python3
"""CPS2 graphics tiles to Saturn 4bpp, with dedupe. Generalised from the AvP tile packer.

CPS2 graphics are 4bpp planar: each 8-pixel group is 4 bytes, one bit plane per byte (byte 0 = plane 0).
Saturn VDP1/VDP2 4bpp is packed, two pixels per byte, high nibble first. CPS2 pen 15 is transparent; on the
Saturn pen 0 is, so pens map p -> p + 1 and 15 -> 0.

Sections (keys as the game's tile codes):
  0 sprite   16x16, 128 bytes per code, from graphics.sprite_base
  1 scroll1  8x8 cell; key = code << 1 | half (left/right 8 px of a 16x8 source), from graphics.scroll_base
  2 scroll2  16x16 as four 8x8 cells TL TR BL BR, from graphics.scroll_base
  3 scroll3  32x32 as four 16x16 characters, each four cells, from graphics.scroll_base

Pack format SGP1 (big endian): magic, then per section: key count, key table offset, data offset; then four
(split index, spill offset) pairs, set to (all ones, 0) here. Key word = key << 16 | payload index (sprites) or
key << 14 | payload index (scroll); an index of all ones means no visible pen. Identical payloads stored once.

usage: cps2_tiles.py GFX_REGION KEYS.json OUT.bin [--config CONFIG]
  KEYS.json: {"sprite": [codes], "scroll1": [...], "scroll2": [...], "scroll3": [...]} (hex strings or ints)
Output is derived from the game. Write it outside git.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

SECTIONS = ("sprite", "scroll1", "scroll2", "scroll3")
MAGIC = 0x53475031
TRANSPARENT = 15


def pens(raw: bytes, off: int, w: int, h: int, stride: int) -> list[list[int]]:
    out = []
    for y in range(h):
        row = []
        for g in range(w // 8):
            o = off + y * stride + g * 4
            b = raw[o:o + 4]
            if len(b) < 4:
                b = b + bytes(4 - len(b))
            for x in range(8):
                m = 0x80 >> x
                row.append((b[3] & m != 0) << 3 | (b[2] & m != 0) << 2 | (b[1] & m != 0) << 1 | (b[0] & m != 0))
        out.append(row)
    return out


def tex(px: list[list[int]]) -> bytes:
    out = bytearray()
    for row in px:
        for x in range(0, len(row), 2):
            out.append((((row[x] + 1) & 15) << 4) | ((row[x + 1] + 1) & 15))
    return bytes(out)


def part(px, y, x, h, w):
    return [r[x:x + w] for r in px[y:y + h]]


def cells16(px) -> bytes:
    return tex(part(px, 0, 0, 8, 8)) + tex(part(px, 0, 8, 8, 8)) + tex(part(px, 8, 0, 8, 8)) + tex(part(px, 8, 8, 8, 8))


def payload(raw: bytes, sec: int, key: int, sprite_base: int = 0, scroll_base: int = 0x800000) -> tuple[bytes, bool]:
    """(Saturn bytes, any visible pen) for one key."""
    if sec == 0:
        px = pens(raw, sprite_base + key * 0x80, 16, 16, 8)
        pl = tex(px)
    elif sec == 1:
        full = pens(raw, scroll_base + (key >> 1) * 0x40, 16, 8, 8)
        px = part(full, 0, 8 if key & 1 else 0, 8, 8)
        pl = tex(px)
    elif sec == 2:
        px = pens(raw, scroll_base + key * 0x80, 16, 16, 8)
        pl = cells16(px)
    else:
        px = pens(raw, scroll_base + key * 0x200, 32, 32, 16)
        pl = b"".join(cells16(part(px, y, x, 16, 16)) for y, x in ((0, 0), (0, 16), (16, 0), (16, 16)))
    return pl, any(p != TRANSPARENT for r in px for p in r)


def pack(raw: bytes, used: list[set[int]], sprite_base: int = 0, scroll_base: int = 0x800000):
    """used: four sets of keys. Returns (pack bytes, [(keys, payload bytes)] per section)."""
    secs = []
    for s in range(4):
        seen: dict[bytes, int] = {}
        data, keys = bytearray(), []
        ks = 16 if s == 0 else 14
        blank = (1 << ks) - 1
        for k in sorted(used[s]):
            pl, vis = payload(raw, s, k, sprite_base, scroll_base)
            if not vis:
                keys.append(k << ks | blank)
                continue
            if pl not in seen:
                seen[pl] = len(seen)
                data += pl
            keys.append(k << ks | seen[pl])
        if len(seen) >= blank or any(k >> 32 for k in keys):
            raise ValueError(f"section {SECTIONS[s]}: too many payloads or key out of range")
        secs.append((keys, bytes(data)))
    hdr = struct.pack(">I", MAGIC)
    off = 4 + 12 * 4 + 8 * 4
    body = bytearray()
    for keys, data in secs:
        ko = off + len(body)
        body += b"".join(struct.pack(">I", k) for k in keys)
        do = off + len(body)
        body += data
        body += b"\0" * (-len(body) % 4)
        hdr += struct.pack(">III", len(keys), ko, do)
    hdr += struct.pack(">II", 0xFFFFFFFF, 0) * 4
    return hdr + bytes(body), [(len(k), len(d)) for k, d in secs]


def read_header(blob: bytes) -> list[tuple[int, int, int]]:
    if struct.unpack_from(">I", blob)[0] != MAGIC:
        raise ValueError("not an SGP1 pack")
    return [struct.unpack_from(">III", blob, 4 + i * 12) for i in range(4)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("gfx", type=pathlib.Path)
    ap.add_argument("keys", type=pathlib.Path)
    ap.add_argument("out", type=pathlib.Path)
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    sb, cb = 0, 0x800000
    if a.config:
        sys.path.insert(0, str(pathlib.Path(__file__).parent))
        import cfg
        c = cfg.load(a.config)
        sb = cfg.get(c, "graphics.sprite_base", sb)
        cb = cfg.get(c, "graphics.scroll_base", cb)
    spec = json.loads(a.keys.read_text())
    used = [{int(k, 16) if isinstance(k, str) else int(k) for k in spec.get(n, [])} for n in SECTIONS]
    blob, sizes = pack(a.gfx.read_bytes(), used, sb, cb)
    a.out.write_bytes(blob)
    for n, (k, d) in zip(SECTIONS, sizes):
        print(f"{n}: {k} keys, {d} payload bytes")
    print("pack bytes", len(blob))
    return 0


if __name__ == "__main__":
    sys.exit(main())
