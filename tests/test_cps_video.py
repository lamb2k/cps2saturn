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

    def test_scan_orders(self):
        self.assertEqual(cps_video.scan(0, 1, 0x21), 0x01 + (1 << 5) + (0x20 << 6))
        self.assertEqual(cps_video.scan(2, 0x41, 9), 0x01 + (1 << 3) + (0x08 << 6))


if __name__ == "__main__":
    unittest.main()
