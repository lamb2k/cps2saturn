import struct
import unittest

import _util  # noqa: F401
import cps2_tiles


def planar_row(pens8):
    """8 pens to 4 CPS2 plane bytes."""
    b = [0, 0, 0, 0]
    for x, p in enumerate(pens8):
        for plane in range(4):
            if p >> plane & 1:
                b[plane] |= 0x80 >> x
    return bytes(b)


class TilesTest(unittest.TestCase):
    def test_planar_round_trip(self):
        row = [0, 1, 2, 3, 12, 13, 14, 15]
        px = cps2_tiles.pens(planar_row(row), 0, 8, 1, 4)
        self.assertEqual(px, [row])
        self.assertEqual(cps2_tiles.tex(px), bytes([0x12, 0x34, 0xDE, 0xF0]))

    def test_pack_dedupe_and_blank(self):
        # Synthetic region: sprite 0 and 1 identical solid, sprite 2 all transparent (pen 15 everywhere).
        solid = planar_row([1] * 8) * 2 * 16          # 16 rows x 2 groups
        clear = planar_row([15] * 8) * 2 * 16
        raw = solid + solid + clear + bytes(0x800000)
        blob, sizes = cps2_tiles.pack(raw, [{0, 1, 2}, set(), set(), set()])
        self.assertEqual(sizes[0], (3, 128))          # three keys, one payload
        hdr = cps2_tiles.read_header(blob)
        n, ko, _ = hdr[0]
        keys = [struct.unpack_from(">I", blob, ko + 4 * i)[0] for i in range(n)]
        self.assertEqual([k & 0xFFFF for k in keys], [0, 0, 0xFFFF])


if __name__ == "__main__":
    unittest.main()
