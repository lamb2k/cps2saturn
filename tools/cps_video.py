#!/usr/bin/env python3
"""A CPS-1 / CPS-Dash frame drawn the way MAME 0.289 draws it: three scroll layers, sprites, and the CPS-B layer
order and priority masks. It is a reference for the Saturn side (what goes in front of what, which pens of a scroll
layer cover sprites) and the oracle tools/video_check.py compares against MAME's own picture.

Inputs for one frame:
  gfxram  GFX RAM, 0x30000 bytes from 0x900000 (scroll maps, row scroll table)
  cps_a   CPS-A registers, 32 words; cps_b  CPS-B registers, 32 words (the values the game last wrote)
  objects the object table the sprite hardware draws (see cps_objects.py)
  gfx     the graphics region (planar tiles, as cps_tiles.py reads it); mapper: the game's cps_tiles.Mapper
  game    from the config: video.layer_control and video.priority (CPS-B register offsets), video.layer_enable_masks
          (three scroll layer enable masks), as the game's CPS-B setup gives them. A priority offset of -1 means
          the game has no such register (MAME's -1): that group's mask is 0 and no pen of it covers sprites
Output: palette indices (0..0xbff) for the 384 x 224 picture; 0xbff is the background pen. Pages: sprites 0x000,
scroll1 0x200, scroll2 0x400, scroll3 0x600. Flip screen, stars and bootleg quirks are not drawn.

How MAME draws it (src/mame/capcom/cps1_v.cpp, described, not copied):
  - CPS-A 0x02/0x04/0x06 hold the scroll map bases (x 256, 0x4000 aligned, inside GFX RAM); 0x0c..0x16 the scroll
    x/y per layer; 0x08 the row scroll table base (0x800 aligned); 0x20 its offset; 0x22 video control (bit 0 row
    scroll on scroll2, bits 2 and 3 enable scroll2 and scroll3).
  - Maps are 64 x 64 tiles of two words (code, attributes). Tile (col, row) is entry
    scroll1: (row & 0x1f) + (col << 5) + ((row & 0x20) << 6); scroll2: (row & 0x0f) + (col << 4) + ((row & 0x30) << 6);
    scroll3: (row & 0x07) + (col << 3) + ((row & 0x38) << 6).
    Attributes: colour bits 0-4, x flip bit 5, y flip bit 6, priority group bits 7-8. scroll3 codes are 14 bits.
    scroll1 tiles are 8 x 8 halves of a 16 x 8 source: even columns the left half, odd columns the right.
  - A screen pixel (x, y) in the 512 x 262 raster (picture origin 64, 16) shows map pixel ((x + scroll x) mod size,
    (y + scroll y) mod size). With row scroll, line y of scroll2 adds row_table[(y + offset) & 0x3ff].
  - Layer control (CPS-B): two bits per draw slot at bits 6, 8, 10, 12 (0 = sprites, 1-3 = scroll layers), bottom
    slot first; scroll layer n is on when layer control & its enable mask (and, for 2 and 3, the video control bit).
  - Each layer draws its pens other than 15. When sprites are the next slot, the layer just drawn also marks its
    pixels whose pen is set in the priority register of the tile's group: sprites do not draw there. Pen 15 is no
    exception: MAME's tilemap transparency (set_transmask) treats all 16 pens alike, so a register with bit 15 set
    lets transparent pixels of that layer hide sprites too. Sprites draw in table order and the first opaque pixel
    at a spot wins.

usage: imported by tools/video_check.py; cps_video.py has no command line.
"""
from __future__ import annotations

import pathlib
import struct
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cps_objects  # noqa: E402
import cps_tiles  # noqa: E402

W, H = 384, 224
X0, Y0 = 64, 16                    # picture origin in the raster
BACKGROUND = 0xBFF
TRANSPARENT = 15
GFX_RAM_SIZE = 0x30000

# CPS-A word registers
OBJ_BASE, SCROLL_BASE, OTHER_BASE, ROWSCROLL_OFFS, VIDEOCONTROL = 0x00, (0x02, 0x04, 0x06), 0x08, 0x20, 0x22
SCROLL_XY = ((0x0C, 0x0E), (0x10, 0x12), (0x14, 0x16))

LAYERS = (   # scroll1..3: tile size, map size in pixels, element bytes, palette base, mapper layer
    dict(tile=8, size=512, elem=0x40, colour=0x20, name="scroll1"),
    dict(tile=16, size=1024, elem=0x80, colour=0x40, name="scroll2"),
    dict(tile=32, size=2048, elem=0x200, colour=0x60, name="scroll3"),
)


def scan(layer: int, col: int, row: int) -> int:
    col &= 0x3F
    if layer == 0:
        return (row & 0x1F) + (col << 5) + ((row & 0x20) << 6)
    if layer == 1:
        return (row & 0x0F) + (col << 4) + ((row & 0x30) << 6)
    return (row & 0x07) + (col << 3) + ((row & 0x38) << 6)


def gfx_base(reg: int, align: int) -> int:
    """Byte offset in GFX RAM of a CPS-A base register value."""
    return ((reg * 256) & ~(align - 1)) & 0x3FFFF


class Frame:
    def __init__(self, gfxram: bytes, cps_a: list[int], cps_b: list[int], game: dict, gfx: bytes,
                 mapper: cps_tiles.Mapper | None):
        self.ram, self.a, self.b, self.game, self.gfx, self.mapper = gfxram, cps_a, cps_b, game, gfx, mapper
        self.cache: dict = {}

    def reg_a(self, off: int) -> int:
        return self.a[off // 2]

    def reg_b(self, off: int) -> int:
        return self.b[off // 2]

    def word(self, byte_off: int) -> int:
        if byte_off + 2 > len(self.ram):
            return 0
        return (self.ram[byte_off] << 8) | self.ram[byte_off + 1]

    def layer_control(self) -> int:
        return self.reg_b(self.game["layer_control"])

    def enabled(self, layer: int) -> bool:
        on = bool(self.layer_control() & self.game["layer_enable_masks"][layer])
        if layer:
            on = on and bool(self.reg_a(VIDEOCONTROL) >> (layer + 1) & 1)
        return on

    def order(self) -> list[int]:
        lc = self.layer_control()
        return [(lc >> s) & 3 for s in (6, 8, 10, 12)]

    def tile(self, layer: int, index: int):
        """(pens rows after flips, palette base, group) for map entry index; pens None when the code does not map."""
        key = (layer, index)
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        spec = LAYERS[layer]
        base = gfx_base(self.reg_a(SCROLL_BASE[layer]), 0x4000)
        code, attr = self.word(base + index * 4), self.word(base + index * 4 + 2)
        if layer == 2:
            code &= 0x3FFF
        mapped = self.mapper.map(spec["name"], code) if self.mapper else code
        px = None
        if mapped is not None:
            count = max(1, len(self.gfx) // spec["elem"])
            addr = (mapped % count) * spec["elem"]
            if layer == 0:
                px = cps_tiles.pens(self.gfx, addr + 4 * (index >> 5 & 1), 8, 8, 8)
            elif layer == 1:
                px = cps_tiles.pens(self.gfx, addr, 16, 16, 8)
            else:
                px = cps_tiles.pens(self.gfx, addr, 32, 32, 16)
            if attr & 0x20:
                px = [r[::-1] for r in px]
            if attr & 0x40:
                px = px[::-1]
        hit = self.cache[key] = (px, ((attr & 0x1F) + spec["colour"]) * 16, (attr >> 7) & 3)
        return hit

    def scroll_line(self, layer: int, vy: int):
        """Yield (pen, palette index, group) for each pixel of picture line vy of a scroll layer."""
        spec = LAYERS[layer]
        size, ts = spec["size"], spec["tile"]
        sx, sy = (self.reg_a(r) for r in SCROLL_XY[layer])
        y = vy + Y0
        if layer == 1 and self.reg_a(VIDEOCONTROL) & 1:
            other = gfx_base(self.reg_a(OTHER_BASE), 0x800)
            sx += self.word(other + 2 * ((y + self.reg_a(ROWSCROLL_OFFS)) & 0x3FF))
        ty = (y + sy) % size
        row, py = ty // ts, ty % ts
        for vx in range(W):
            tx = (vx + X0 + sx) % size
            px, colour, group = self.tile(layer, scan(layer, tx // ts, row))
            pen = TRANSPARENT if px is None else px[py][tx % ts]
            yield pen, colour + pen, group


def render(frame: Frame, objects: bytes, g: dict | None = None) -> list[int]:
    """Palette indices of the whole picture, row by row. g gives the object format; the picture is always MAME's
    full 384 x 224, whatever crop a config's graphics.objects sets for the Saturn side."""
    g = dict(g or cps_objects.CPS1_DEFAULT, view_x=X0, view_y=Y0, view_w=W, view_h=H)
    pix = [BACKGROUND] * (W * H)
    pri = [0] * (W * H)
    prio = [frame.reg_b(o) if o >= 0 else 0 for o in frame.game["priority"]]   # -1: no register, mask 0

    def scroll(layer: int, high: bool):
        if not frame.enabled(layer):
            return
        for vy in range(H):
            o = vy * W
            for vx, (pen, index, group) in enumerate(frame.scroll_line(layer, vy)):
                if high:
                    # pen is opaque in the front mask (mask = priority ^ 0xffff). Pen 15 included, as in MAME.
                    if (prio[group] >> pen) & 1:
                        pri[o + vx] |= 1
                elif pen != TRANSPARENT:
                    pix[o + vx] = index

    def sprites():
        sm = (lambda c: frame.mapper.map("sprites", c)) if frame.mapper else None
        count = max(1, len(frame.gfx) // 0x80)
        cache: dict[int, list[list[int]]] = {}
        for t, on in cps_objects.tiles(objects, g, sm):
            if not on:
                continue
            code = t.code % count
            px = cache.get(code)
            if px is None:
                px = cache[code] = cps_tiles.pens(frame.gfx, code * 0x80, 16, 16, 8)
            for y in range(16):
                sy = t.sy + y
                if not 0 <= sy < H:
                    continue
                r = px[15 - y if t.fy else y]
                for x in range(16):
                    sx = t.sx + x
                    if 0 <= sx < W:
                        pen = r[15 - x if t.fx else x]
                        if pen != TRANSPARENT:
                            i = sy * W + sx
                            if pri[i] & 0x1F not in (1, 31):
                                pix[i] = t.bank * 16 + pen
                            pri[i] = 31

    def draw(slot: int):
        if slot == 0:
            sprites()
        else:
            scroll(slot - 1, False)

    order = frame.order()
    for k, slot in enumerate(order):
        draw(slot)
        if k + 1 < len(order) and order[k + 1] == 0 and slot != 0:
            scroll(slot - 1, True)
    return pix


def regs(blob: bytes) -> tuple[list[int], list[int]]:
    """CPS-A and CPS-B words from a 0x80-byte dump (0x40 each, big-endian)."""
    words = list(struct.unpack(">64H", blob[:0x80]))
    return words[:32], words[32:]
