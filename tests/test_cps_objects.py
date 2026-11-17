import io
import pathlib
import struct
import tempfile
import unittest
from contextlib import redirect_stdout

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

    def test_bank_sizes_must_be_positive_powers_of_two(self):
        for sizes in ([0, 0x100], [0x300, 0x100]):
            with self.assertRaises(ValueError):
                cps_tiles.Mapper({"bank_sizes": sizes, "ranges": [["sprites", 0, 0xFF, 0]]})
        # A bank no range uses may stay 0 (dino's mapper has two empty banks).
        self.assertEqual(cps_tiles.Mapper({"bank_sizes": [0x100, 0], "ranges": [["sprites", 0, 0xFF, 0]]}).map(
            "sprites", 0x10), 0x10)

    def test_rom_key_space_is_not_mapped_again(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "c.yaml").write_text(CONFIG)
            (d / "gfx.bin").write_bytes(bytes([0, 0, 0, 0]) * 2 * 16 * 0xC2)         # 0xc2 tiles of pen 0
            for space, want in (("rom", (1, 128)), ("game", (1, 0))):
                (d / "keys.json").write_text(json.dumps({"key_space": space, "sprite": ["c1"]}))
                f = io.StringIO()
                with redirect_stdout(f):
                    cps_tiles.main([str(d / "gfx.bin"), str(d / "keys.json"), str(d / "out.bin"),
                                    "--config", str(d / "c.yaml")])
                # rom: 0xc1 is read as tile 0xc1. game: 0xc1 << 1 = 0x182 is past the mapper's range: blank.
                self.assertIn(f"sprite: {want[0]} keys, {want[1]} payload bytes", f.getvalue(), space)

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


CONFIG = """game:
  set: test
  board: cpsdash
graphics:
  mapper:
    bank_sizes: [0x100, 0x100, 0, 0]
    ranges:
      - ["sprites", 0x020, 0x0ff, 1]
"""


class CliTest(unittest.TestCase):
    """decode and funnel with a CPS-Dash config whose mapper is not the identity."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        d = pathlib.Path(self.dir.name)
        self.config = d / "c.yaml"
        self.config.write_text(CONFIG)
        # Entry 0: 2x1 block, base 0x40 (<< 1 = 0x80, bank 1: tile (0x100 + 0x80) >> 1 = 0xc0): tiles 0xc0, 0xc1.
        # Entry 1: 2x1 block, base 0x00 (<< 1 = 0: no range): not drawn at all, even though 0x01 would map.
        self.objram = d / "obj.bin"
        self.objram.write_bytes(entry(64, 16, 0x40, 0x0100) + entry(64, 48, 0x00, 0x0100) + END + bytes(0x7E8))
        self.d = d

    def tearDown(self):
        self.dir.cleanup()

    def run_cli(self, *args):
        f = io.StringIO()
        with redirect_stdout(f):
            rc = cps_objects.main(list(args))
        return rc, f.getvalue().splitlines()

    def test_decode_maps_each_base_once_and_skips_unmapped_bases(self):
        rc, lines = self.run_cli("decode", str(self.objram), "--config", str(self.config))
        self.assertEqual(rc, 0)
        self.assertTrue(lines[0].startswith("# codes: graphics ROM tiles"))
        self.assertEqual([l.split()[-1] for l in lines[1:]], ["000c0", "000c1"])

    def test_decode_without_a_mapper_prints_game_codes(self):
        rc, lines = self.run_cli("decode", str(self.objram))
        self.assertEqual(lines[0], "# codes: game codes")

    def test_funnel_counts_in_rom_tile_space_with_solid(self):
        frames = self.d / "frames.bin"
        frames.write_bytes(b"HEAD" + self.objram.read_bytes())       # one record: 4 bytes, then the table
        solid = self.d / "solid.txt"
        solid.write_text("c1\n")                                     # ROM tile 0xc1 has a visible pen; 0xc0 does not
        rc, lines = self.run_cli("funnel", str(frames), "--stride", hex(4 + 0x800), "--offset", "4",
                                 "--solid", str(solid), "--config", str(self.config))
        self.assertEqual(rc, 0)
        stats = {l.split()[0]: int(float(l.split()[2])) for l in lines[1:]}
        self.assertEqual((stats["tiles"], stats["empty"], stats["commands"]), (2, 1, 1))


if __name__ == "__main__":
    unittest.main()
