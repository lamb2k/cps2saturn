#!/usr/bin/env python3
"""CPS graphics tiles to Saturn 4bpp, with dedupe, for CPS-2 and CPS-1 / CPS-Dash. From the AvP tile packer.

CPS graphics are 4bpp planar: each 8-pixel group is 4 bytes, one bit plane per byte (byte 0 = plane 0), the layout
MAME decodes (gfx_cps1). GFX_REGION is MAME's graphics region in that order: for CPS-2 after MAME's unshuffle;
CPS-1 and CPS-Dash ROMs need none. Saturn VDP1/VDP2 4bpp is packed, two pixels per byte, high nibble first. CPS
pen 15 is transparent; on the Saturn pen 0 is, so pens map p -> p + 1 and 15 -> 0.

Sections (keys as the game's tile codes):
  0 sprite   16x16, 128 bytes per tile, from graphics.sprite_base
  1 scroll1  8x8 cell; key = code << 1 | half (left/right 8 px of a 16x8 source), from graphics.scroll_base
  2 scroll2  16x16 as four 8x8 cells TL TR BL BR, from graphics.scroll_base
  3 scroll3  32x32 as four 16x16 characters, each four cells, from graphics.scroll_base
The bases default by board (CPS-2: 0 and 0x800000; CPS-1, CPS-Dash: 0 and 0).

CPS-1 and CPS-Dash map a game code to a graphics ROM tile through the game's PAL mapper, given in the config as
graphics.mapper (fill it from your own work; the kit holds no game's table):
  mapper:
    bank_sizes: [0x8000, 0x8000, 0, 0]          # in shifted code units, as MAME's tables give them
    ranges:                                    # [layers, first, last, bank]; layers: sprites scroll1 scroll2 scroll3
      - ["sprites scroll1 scroll2 scroll3", 0x0000, 0x7fff, 0]
The code is shifted by the layer (sprites 1, scroll1 0, scroll2 1, scroll3 3), looked up in the first range that
holds it and allows the layer, rebased on the sizes of the banks before it, and shifted back. A code no range
takes has no tile: its key is packed as blank. Without a mapper, codes are tile numbers (CPS-2).
Key space. Codes are mapped exactly once. KEYS.json may say "key_space": "game" (the default: keys are the game's
codes and the packer maps each one) or "rom" (keys are already graphics ROM tile numbers, as cps_objects.py
prints them with a mapper, and the packer reads them as they are). Prefer "rom" for sprites: the CPS-1 sprite
hardware maps a block's base code and then steps through the 16-code row, so a block that crosses a range edge
can differ from its game codes mapped one by one.

Pack format SGP1 (big endian): magic, then per section: key count, key table offset, data offset; then four
(split index, spill offset) pairs, set to (all ones, 0) here. Key word = key << 16 | payload index (sprites) or
key << 14 | payload index (scroll); an index of all ones means no visible pen. Identical payloads stored once.

usage: cps_tiles.py GFX_REGION KEYS.json OUT.bin [--config CONFIG]
  KEYS.json: {"sprite": [codes], "scroll1": [...], "scroll2": [...], "scroll3": [...]} (hex strings or ints),
             optionally "key_space": "game" | "rom"
Output is derived from the game. Write it outside git.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import boards  # noqa: E402
import cfg  # noqa: E402

SECTIONS = ("sprite", "scroll1", "scroll2", "scroll3")
MAGIC = 0x53475031
TRANSPARENT = 15
LAYERS = {"sprites": 1, "scroll1": 0, "scroll2": 1, "scroll3": 3}   # layer name -> code shift
SECTION_LAYER = ("sprites", "scroll1", "scroll2", "scroll3")


class Mapper:
    """A game's graphics ROM mapper (graphics.mapper in the config)."""

    def __init__(self, spec: dict):
        self.sizes = list(spec["bank_sizes"])
        self.ranges = []
        for layers, first, last, bank in spec["ranges"]:
            names = set(layers.replace("|", " ").replace(",", " ").split()) if isinstance(layers, str) else set(layers)
            bad = names - set(LAYERS)
            if bad or not names:
                raise ValueError(f"graphics.mapper: unknown layer {sorted(bad)}; use {', '.join(LAYERS)}")
            if not 0 <= bank < len(self.sizes):
                raise ValueError(f"graphics.mapper: bank {bank} has no size")
            size = self.sizes[bank]
            if size <= 0 or size & (size - 1):
                raise ValueError(f"graphics.mapper: bank {bank} size {size:#x} must be a positive power of two "
                                 "(fill bank_sizes from the game's mapper)")
            self.ranges.append((names, first, last, bank))

    def map(self, layer: str, code: int) -> int | None:
        shift = LAYERS[layer]
        c = code << shift
        for names, first, last, bank in self.ranges:
            if first <= c <= last and layer in names:
                return (sum(self.sizes[:bank]) + (c & (self.sizes[bank] - 1))) >> shift
        return None


def mapper_from(c: dict) -> Mapper | None:
    spec = cfg.get(c, "graphics.mapper")
    return Mapper(spec) if spec else None


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


def payload(raw: bytes, sec: int, key: int, sprite_base: int = 0, scroll_base: int = 0x800000,
            mapper: Mapper | None = None) -> tuple[bytes, bool]:
    """(Saturn bytes, any visible pen) for one key. A key the mapper does not take is (b"", False)."""
    if mapper is not None:
        half = key & 1 if sec == 1 else 0
        tile = mapper.map(SECTION_LAYER[sec], key >> 1 if sec == 1 else key)
        if tile is None:
            return b"", False
        key = tile << 1 | half if sec == 1 else tile
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


def pack(raw: bytes, used: list[set[int]], sprite_base: int = 0, scroll_base: int = 0x800000,
         mapper: Mapper | None = None):
    """used: four sets of keys. Returns (pack bytes, [(keys, payload bytes)] per section)."""
    secs = []
    for s in range(4):
        seen: dict[bytes, int] = {}
        data, keys = bytearray(), []
        ks = 16 if s == 0 else 14
        blank = (1 << ks) - 1
        for k in sorted(used[s]):
            pl, vis = payload(raw, s, k, sprite_base, scroll_base, mapper)
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
    c = cfg.load(a.config) if a.config else {}
    sb = cfg.get(c, "graphics.sprite_base", boards.value(c, "gfx_sprite_base"))
    cb = cfg.get(c, "graphics.scroll_base", boards.value(c, "gfx_scroll_base"))
    mapper = mapper_from(c)
    spec = json.loads(a.keys.read_text())
    space = spec.get("key_space", "game")
    if space not in ("game", "rom"):
        sys.exit(f'KEYS.json key_space {space!r}: expected "game" or "rom"')
    if space == "rom":
        mapper = None                            # keys are ROM tiles already: never map them twice
    used = [{int(k, 16) if isinstance(k, str) else int(k) for k in spec.get(n, [])} for n in SECTIONS]
    blob, sizes = pack(a.gfx.read_bytes(), used, sb, cb, mapper)
    a.out.write_bytes(blob)
    for n, (k, d) in zip(SECTIONS, sizes):
        print(f"{n}: {k} keys, {d} payload bytes")
    print("pack bytes", len(blob))
    return 0


if __name__ == "__main__":
    sys.exit(main())
