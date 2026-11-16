import struct
import unittest

import _util  # noqa: F401
import cps_objects
import cps_tiles

G1 = cps_objects.CPS1_DEFAULT


def entry(x, y, code, attr):
    return struct.pack(">4H", x, y, code, attr)


END = entry(0, 0, 0, 0xFF00)


def placed(obj, g=G1, mapper=None):
    return [(t.sx, t.sy, t.code, t.bank, t.fx, t.fy) for t, _ in cps_objects.tiles(obj, g, mapper)]


class Cps1ObjectsTest(unittest.TestCase):
    def test_screen_origin_and_end_marker(self):
        # CPS-1 coordinates are raw 9-bit; the visible picture starts at (64, 16).
        obj = entry(64, 16, 0x123, 0x0005) + END + entry(64, 16, 0x456, 0)
        self.assertEqual(placed(obj), [(0, 0, 0x123, 5, 0, 0)])

    def test_cps2_end_marker_in_y_does_not_end_a_cps1_list(self):
        obj = entry(64, 0x8000 | 16, 0x10, 0) + END
        self.assertEqual(len(placed(obj)), 1)

    def test_block_wraps_inside_a_16_code_row_in_every_flip(self):
        # 3 wide, 2 high, base code 0x2e: columns 0x2e, 0x2f, 0x20 (wrap), rows add 0x10.
        for attr, codes in (
                (0x1200, [0x2E, 0x2F, 0x20, 0x3E, 0x3F, 0x30]),
                (0x1220, [0x20, 0x2F, 0x2E, 0x30, 0x3F, 0x3E]),          # x flip
                (0x1240, [0x3E, 0x3F, 0x30, 0x2E, 0x2F, 0x20]),          # y flip
                (0x1260, [0x30, 0x3F, 0x3E, 0x20, 0x2F, 0x2E])):         # both
            got = placed(entry(64, 16, 0x2E, attr) + END)
            self.assertEqual([c for _, _, c, *_ in got], codes, hex(attr))
            self.assertEqual([(x, y) for x, y, *_ in got], [(0, 0), (16, 0), (32, 0), (0, 16), (16, 16), (32, 16)])

    def test_coordinates_wrap_at_9_bits_without_drawing_on_the_left(self):
        obj = entry(0x1F0, 16, 1, 0x0100) + END        # 2 wide: x 0x1f0 then 0x200 & 0x1ff = 0
        got = placed(obj)
        self.assertEqual([(x, on) for (x, *_), (_, on) in zip(got, cps_objects.tiles(obj, G1))],
                         [(0x1F0 - 64, False), (-64, False)])

    def test_mapper_maps_the_base_code_and_skips_unmapped_sprites(self):
        m = cps_tiles.Mapper({"bank_sizes": [0x100, 0x100, 0, 0],
                              "ranges": [["sprites", 0x000, 0x0FF, 1], ["scroll1", 0x100, 0x1FF, 0]]})
        obj = entry(64, 16, 0x40, 0x0100) + entry(64, 16, 0x90, 0) + END
        # 0x40 << 1 = 0x80 lies in the sprite range on bank 1: (0x100 + 0x80) >> 1 = 0xc0. 0x90 << 1 = 0x120 is scroll1 only.
        self.assertEqual([c for _, _, c, *_ in placed(obj, mapper=lambda c: m.map("sprites", c))], [0xC0, 0xC1])

    def test_board_picks_the_format(self):
        self.assertEqual(cps_objects.geometry(None)["format"], "cps2")
        self.assertEqual(cps_objects.geometry(None, board="cpsdash")["format"], "cps1")


class MapperTest(unittest.TestCase):
    def test_shift_per_layer_and_bank_base(self):
        m = cps_tiles.Mapper({"bank_sizes": [0x8000, 0x4000, 0, 0],
                              "ranges": [["sprites scroll2", 0x0000, 0x7FFF, 0],
                                         ["sprites scroll1 scroll2 scroll3", 0x8000, 0xBFFF, 1]]})
        self.assertEqual(m.map("sprites", 0x1234), 0x1234)
        self.assertEqual(m.map("scroll1", 0x1234), None)             # 0x1234 lies in bank 0, which scroll1 cannot use
        self.assertEqual(m.map("scroll1", 0x8001), 0x8001)
        self.assertEqual(m.map("scroll3", 0x1001), 0x1001)            # << 3 = 0x8008: bank 1
        self.assertEqual(m.map("sprites", 0x6000), None)              # << 1 = 0xc000: past every range

    def test_unknown_layer_name_is_refused(self):
        with self.assertRaises(ValueError):
            cps_tiles.Mapper({"bank_sizes": [1], "ranges": [["sprite", 0, 1, 0]]})

    def test_pack_reads_mapped_tiles_and_blanks_unmapped_keys(self):
        solid = bytes([0, 0, 0, 0]) * 2 * 16                          # pen 0 everywhere: visible
        other = bytes([0xFF, 0, 0, 0]) * 2 * 16                       # pen 1 everywhere
        raw = solid + other
        m = cps_tiles.Mapper({"bank_sizes": [0x2, 0x2, 0, 0], "ranges": [["sprites", 0, 1, 1]]})
        blob, sizes = cps_tiles.pack(raw, [{0, 5}, set(), set(), set()], 0, 0, mapper=m)
        # key 0: 0 << 1 = 0 is in the range on bank 1: (2 + 0) >> 1 = tile 1 (pen 1). key 5: 10 is out of range.
        n, ko, do = cps_tiles.read_header(blob)[0]
        keys = [struct.unpack_from(">I", blob, ko + 4 * i)[0] for i in range(n)]
        self.assertEqual([k & 0xFFFF for k in keys], [0, 0xFFFF])
        self.assertEqual(blob[do:do + 128], bytes([0x22]) * 128)       # pen 1 -> Saturn pen 2


if __name__ == "__main__":
    unittest.main()
