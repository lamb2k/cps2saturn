import struct
import unittest

import _util  # noqa: F401
import cps_video

GAME = dict(layer_control=0x0A, priority=[0x0C, 0x0E, 0x00, 0x02], layer_enable_masks=[0x02, 0x04, 0x10])


def tile16(pen):
    """A 16x16 planar tile of one pen (also an 8x8 element when read as one)."""
    b = bytes([0xFF if pen >> plane & 1 else 0 for plane in range(4)])
    return b * 2 * 16


GFX = tile16(15) + tile16(3) + tile16(5)          # 0 clear, 1 solid pen 3, 2 solid pen 5 (sprites, scroll2: 0x80 each)
SCROLL2 = 0x9040                                 # CPS-A base value: GFX RAM offset 0x4000


def frame(lc, vc=0x04, prio0=0, scroll=(0, 0), rows=None, other_offs=0):
    ram = bytearray(cps_video.GFX_RAM_SIZE)
    # scroll2 map: tile (col 4, row 1) shows at picture (0, 0) with no scroll. Code 1, colour 2.
    i = cps_video.scan(1, 4, 1)
    struct.pack_into(">HH", ram, 0x4000 + i * 4, 1, 2)
    a = [0] * 32
    a[0x04 // 2] = SCROLL2
    a[0x10 // 2], a[0x12 // 2] = scroll
    a[0x22 // 2] = vc
    if rows is not None:
        a[0x08 // 2] = 0x9100                   # row scroll table at GFX RAM offset 0x10000
        a[0x20 // 2] = other_offs
        for line, dx in rows.items():
            struct.pack_into(">H", ram, 0x10000 + 2 * line, dx & 0xFFFF)
        a[0x22 // 2] |= 1
    b = [0] * 32
    b[0x0A // 2] = lc
    b[0x0C // 2] = prio0
    return cps_video.Frame(bytes(ram), a, b, GAME, GFX, None)


def order(*slots):
    return sum(s << (6 + 2 * k) for k, s in enumerate(slots))


SPRITE = struct.pack(">4H", 64, 16, 2, 0x0001) + struct.pack(">4H", 0, 0, 0, 0xFF00)   # code 2 at (0, 0), bank 1
S2 = (2 + 0x40) * 16 + 3                                                               # scroll2 colour 2, pen 3
SP = 1 * 16 + 5


class VideoTest(unittest.TestCase):
    def test_scroll2_tile_lands_at_the_picture_origin(self):
        pix = cps_video.render(frame(0x04 | order(2, 0, 1, 3)), b"")
        self.assertEqual(pix[0], S2)
        self.assertEqual(pix[15 * cps_video.W + 15], S2)
        self.assertEqual(pix[16], cps_video.BACKGROUND)

    def test_scroll_moves_the_map_left_and_up(self):
        pix = cps_video.render(frame(0x04 | order(2, 0, 1, 3), scroll=(8, 4)), b"")
        self.assertEqual(pix[0], S2)                     # map (72, 20) is still inside the tile
        self.assertEqual(pix[8], cps_video.BACKGROUND)    # map (80, 20) is past it
        self.assertEqual(pix[12 * cps_video.W], cps_video.BACKGROUND)

    def test_sprites_above_or_below_by_slot(self):
        above = cps_video.render(frame(0x04 | order(2, 0, 1, 3)), SPRITE)
        below = cps_video.render(frame(0x04 | order(0, 2, 1, 3)), SPRITE)
        self.assertEqual((above[0], below[0]), (SP, S2))

    def test_priority_pens_of_the_layer_below_cover_sprites(self):
        pix = cps_video.render(frame(0x04 | order(2, 0, 1, 3), prio0=1 << 3), SPRITE)
        self.assertEqual(pix[0], S2)
        other_pen = cps_video.render(frame(0x04 | order(2, 0, 1, 3), prio0=1 << 4), SPRITE)
        self.assertEqual(other_pen[0], SP)

    def test_layer_enable_and_video_control(self):
        self.assertEqual(cps_video.render(frame(order(2, 0, 1, 3)), b"")[0], cps_video.BACKGROUND)
        self.assertEqual(cps_video.render(frame(0x04 | order(2, 0, 1, 3), vc=0), b"")[0], cps_video.BACKGROUND)

    def test_row_scroll_shifts_one_line(self):
        # Line 3 of the picture is raster line 19; its table entry adds 16 px of x scroll there only.
        pix = cps_video.render(frame(0x04 | order(2, 0, 1, 3), rows={19: 16}), b"")
        self.assertEqual(pix[3 * cps_video.W], cps_video.BACKGROUND)
        self.assertEqual(pix[2 * cps_video.W], S2)
        shifted = cps_video.render(frame(0x04 | order(2, 0, 1, 3), rows={23: 16}, other_offs=4), b"")
        self.assertEqual(shifted[3 * cps_video.W], cps_video.BACKGROUND)

    def test_undefined_priority_registers_never_cover_sprites(self):
        # MAME marks a missing priority register with -1. The last CPS-B register must not stand in for it.
        game = dict(GAME, priority=[-1, -1, -1, -1])
        f = frame(0x04 | order(2, 0, 1, 3))
        f.b[31] = 0xFFFF
        f.game = game
        self.assertEqual(cps_video.render(f, SPRITE)[0], SP)

    def test_pen_15_follows_the_priority_register_as_in_mame(self):
        # MAME's set_transmask treats all 16 pens alike: with bit 15 set, transparent pixels of the layer below the
        # sprites hide them too. Picture (32, 0) is map (96, 16): an empty scroll2 tile, all pen 15.
        pix = cps_video.render(frame(0x04 | order(2, 0, 1, 3), prio0=1 << 15),
                               struct.pack(">4H", 96, 16, 2, 0x0001) + struct.pack(">4H", 0, 0, 0, 0xFF00))
        self.assertEqual(pix[32], cps_video.BACKGROUND)
        shown = cps_video.render(frame(0x04 | order(2, 0, 1, 3), prio0=1 << 14),
                                 struct.pack(">4H", 96, 16, 2, 0x0001) + struct.pack(">4H", 0, 0, 0, 0xFF00))
        self.assertEqual(shown[32], SP)

    def test_scan_orders(self):
        self.assertEqual(cps_video.scan(0, 1, 0x21), 0x01 + (1 << 5) + (0x20 << 6))
        self.assertEqual(cps_video.scan(2, 0x41, 9), 0x01 + (1 << 3) + (0x08 << 6))


if __name__ == "__main__":
    unittest.main()


def solid(pen, nbytes):
    """nbytes of planar data, every pixel the given pen."""
    return bytes([0xFF if pen >> plane & 1 else 0 for plane in range(4)]) * (nbytes // 4)


def scroll_frame(layer, base_reg, entries, gfx, vc, lc, mapper=None):
    """A frame with one scroll layer's map entries {index: (code, attr)}."""
    ram = bytearray(cps_video.GFX_RAM_SIZE)
    base = cps_video.gfx_base(base_reg, 0x4000)
    for index, (code, attr) in entries.items():
        struct.pack_into(">HH", ram, base + index * 4, code, attr)
    a, b = [0] * 32, [0] * 32
    a[cps_video.SCROLL_BASE[layer] // 2] = base_reg
    a[0x22 // 2] = vc
    b[0x0A // 2] = lc
    return cps_video.Frame(bytes(ram), a, b, GAME, gfx, mapper)


class ScrollLayerTest(unittest.TestCase):
    def test_scroll1_alternates_left_and_right_halves_by_column(self):
        # Element 1 (0x40 bytes): left 8 px pen 3, right 8 px pen 5. Picture x 0-7 is map column 8 (even, left
        # half), x 8-15 is column 9 (odd, right half). Same code in both.
        half = solid(3, 4) + solid(5, 4)
        gfx = solid(15, 0x40) + half * 8
        entries = {cps_video.scan(0, 8, 2): (1, 1), cps_video.scan(0, 9, 2): (1, 1)}
        pix = cps_video.render(scroll_frame(0, 0x9000, entries, gfx, 0, 0x02 | order(2, 3, 0, 1)), b"")
        self.assertEqual((pix[0], pix[7], pix[8], pix[15]), ((1 + 0x20) * 16 + 3,) * 2 + ((1 + 0x20) * 16 + 5,) * 2)

    def test_scroll3_codes_are_14_bits(self):
        gfx = solid(15, 0x200) + solid(3, 0x200)
        entries = {cps_video.scan(2, 2, 0): (0x4001, 2)}         # picture (0, 0) is map (64, 16): column 2, row 0
        pix = cps_video.render(scroll_frame(2, 0x9080, entries, gfx, 0x08, 0x10 | order(3, 2, 0, 1)), b"")
        self.assertEqual(pix[0], (2 + 0x60) * 16 + 3)

    def test_scroll_tile_flips(self):
        # Scroll2 tile 1: pen 1 at its top-left pixel only.
        one = bytearray(solid(15, 0x80))
        one[3] &= 0x7F                                              # plane 3 of pixel (0, 0) off: pen 7
        one[2] &= 0x7F
        one[1] &= 0x7F                                              # pen 1
        gfx = solid(15, 0x80) + bytes(one)
        at = {0x00: (0, 0), 0x20: (15, 0), 0x40: (0, 15), 0x60: (15, 15)}
        for attr, (x, y) in at.items():
            entries = {cps_video.scan(1, 4, 1): (1, attr)}
            pix = cps_video.render(scroll_frame(1, SCROLL2, entries, gfx, 0x04, 0x04 | order(2, 0, 1, 3)), b"")
            lit = [i for i, v in enumerate(pix) if v != cps_video.BACKGROUND]
            self.assertEqual(lit, [y * cps_video.W + x], hex(attr))

    def test_mapper_on_scroll_layers(self):
        import cps_tiles
        m = cps_tiles.Mapper({"bank_sizes": [0x2, 0x2, 0, 0], "ranges": [["scroll2", 0x0A, 0x0B, 1]]})
        gfx = solid(15, 0x80) + solid(3, 0x80)
        # Code 5 << 1 = 0x0a: bank 1, tile (2 + 0) >> 1 = 1. Code 6 << 1 = 0x0c: no range, drawn transparent.
        for code, want in ((5, (2 + 0x40) * 16 + 3), (6, cps_video.BACKGROUND)):
            entries = {cps_video.scan(1, 4, 1): (code, 2)}
            pix = cps_video.render(scroll_frame(1, SCROLL2, entries, gfx, 0x04, 0x04 | order(2, 0, 1, 3), m), b"")
            self.assertEqual(pix[0], want, code)
