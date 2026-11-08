import struct
import unittest

import _util  # noqa: F401
import cps2_objects


def entry(x, y, code, attr):
    return struct.pack(">4H", x, y, code, attr)


class ObjectsTest(unittest.TestCase):
    def test_block_and_end_marker(self):
        # 2x1 block at screen (0, 0): x = view_x - x_bias + relative_dx ... with no relative flag:
        g = cps2_objects.DEFAULT
        x = g["view_x"] - (g["x_bias"] - g["relative_dx"])
        y = g["view_y"] - (g["y_bias"] - g["relative_dy"])
        obj = entry(x, y, 0x10, 0x0103) + entry(0, 0x8000, 0, 0) + entry(x, y, 0x20, 0)
        tiles = list(cps2_objects.tiles(obj))
        self.assertEqual(len(tiles), 2)
        self.assertEqual([(t.sx, t.sy, t.code, t.bank) for t, _ in tiles], [(0, 0, 0x10, 3), (16, 0, 0x11, 3)])
        n = cps2_objects.funnel(obj, {0x10})
        self.assertEqual((n["tiles"], n["commands"], n["empty"], n["runs"], n["banks"]), (2, 1, 1, 1, 1))

    def test_x_flip_and_offscreen(self):
        g = cps2_objects.DEFAULT
        x = g["view_x"] - (g["x_bias"] - g["relative_dx"])
        y = g["view_y"] - (g["y_bias"] - g["relative_dy"])
        obj = entry(x, y, 0x10, 0x0100 | 0x20) + entry((x + 400) & 0x3FF, y, 0x30, 0) + entry(0, 0x8000, 0, 0)
        t = list(cps2_objects.tiles(obj))
        self.assertEqual([c.code for c, _ in t[:2]], [0x11, 0x10])
        self.assertFalse(t[2][1])


if __name__ == "__main__":
    unittest.main()
