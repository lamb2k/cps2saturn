import copy
import io
import pathlib
import struct
import tempfile
import unittest
from contextlib import redirect_stdout

import _util  # noqa: F401
import cfg
import cps_objects
import sprite_check

G = dict(cps_objects.CPS1_DEFAULT, view_w=32, view_h=16)


def tile(pen_of):
    """One 16x16 planar tile; pen_of(x, y) gives each pen."""
    out = bytearray()
    for y in range(16):
        for half in range(2):
            b = [0, 0, 0, 0]
            for x in range(8):
                p = pen_of(half * 8 + x, y)
                for plane in range(4):
                    if p >> plane & 1:
                        b[plane] |= 0x80 >> x
            out += bytes(b)
    return bytes(out)


def entry(x, y, code, attr):
    return struct.pack(">4H", x, y, code, attr)


END = entry(0, 0, 0, 0xFF00)
PAL = [bytes((i & 0xFF, i >> 8, 0)) for i in range(0x200)] + [b"\x00\x00\xff"]


def pixel(img, x, y):
    w, _, rgb = img
    return rgb[(y * w + x) * 3:(y * w + x) * 3 + 3]


class RenderTest(unittest.TestCase):
    def setUp(self):
        # Tile 0: pen 1 in the left column only, transparent elsewhere. Tile 1: solid pen 2.
        self.gfx = tile(lambda x, y: 1 if x == 0 else 15) + tile(lambda x, y: 2)

    def test_first_entry_is_on_top_and_pen_15_shows_through(self):
        obj = entry(64, 16, 0, 0x0003) + entry(64, 16, 1, 0x0001) + END
        img = sprite_check.render(obj, self.gfx, PAL, G, None)
        self.assertEqual(pixel(img, 0, 0), PAL[3 * 16 + 1])    # entry 0, bank 3, pen 1
        self.assertEqual(pixel(img, 1, 0), PAL[1 * 16 + 2])    # entry 1 shows through entry 0's pen 15
        self.assertEqual(pixel(img, 20, 0), PAL[0x200])        # background pen

    def test_x_flip_mirrors_the_tile(self):
        img = sprite_check.render(entry(64, 16, 0, 0x0020) + END, self.gfx, PAL, G, None)
        self.assertEqual(pixel(img, 15, 0), PAL[1])
        self.assertEqual(pixel(img, 0, 0), PAL[0x200])

    def test_mapper_picks_the_tile(self):
        img = sprite_check.render(entry(64, 16, 7, 0) + END, self.gfx, PAL, G, lambda c: 1 if c == 7 else None)
        self.assertEqual(pixel(img, 5, 5), PAL[2])


class CaptureTest(unittest.TestCase):
    def config(self, **video):
        c = copy.deepcopy(cfg.load(_util.EXAMPLE))
        c["game"]["board"] = "cpsdash"
        del c["ram"]["object_base"], c["ram"]["object_size"]
        c["video"] = video
        return c

    def test_layer_control_is_required(self):
        with self.assertRaises(SystemExit):
            sprite_check.layer_control(self.config())

    def test_layer_control_address_is_cps_b_plus_the_offset(self):
        self.assertEqual(sprite_check.layer_control(self.config(layer_control=0x0A, layer_enable_mask=0x16)),
                         "0x80014a,0x16")
        self.assertEqual(sprite_check.layer_control(self.config(cps_b=0x800160, layer_control=0x0A,
                                                                layer_enable_mask=0x16)), "0x80016a,0x16")

    def test_dry_run_wraps_the_golden_run(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "c.yaml"
            text = _util.EXAMPLE.read_text().replace("board: cps2", "board: cpsdash")
            text = text.replace("  object_base: 0x708000\n  object_size: 0x2000\n", "")
            path.write_text(text + "\nvideo:\n  layer_control: 0x0a\n  layer_enable_mask: 0x16\n")
            f = io.StringIO()
            with redirect_stdout(f):
                sprite_check.main(["capture", "--config", str(path), "--name", "x", "--frames", "5,3", "--last", "9",
                                   "--out-root", d, "--dry-run"])
            out = f.getvalue()
        self.assertIn("CPS2SAT_FRAMES=3,5", out)
        self.assertIn("CPS2SAT_OBJ_REG=0x800100,0x800", out)
        self.assertIn("CPS2SAT_DELTA=1", out)
        self.assertIn("sprite_frames.lua", out.splitlines()[-1])

    def test_frames_must_come_before_the_last_frame(self):
        with self.assertRaises(SystemExit):
            sprite_check.main(["capture", "--config", str(_util.EXAMPLE), "--name", "x", "--frames", "9", "--last",
                               "9", "--dry-run"])

    def test_lua_reads_the_names_the_tool_sets(self):
        lua = (_util.TOOLS / "mame" / "sprite_frames.lua").read_text()
        for name in ("CPS2SAT_GOLDEN_LUA", "CPS2SAT_LAYER_CTRL", "CPS2SAT_FRAMES", "CPS2SAT_FRAMES_DIR",
                     "CPS2SAT_GFX_OUT", "CPS2SAT_GFX_REGION"):
            self.assertIn(f'"{name}"', lua)
        self.assertIn("cps2sat_golden_irq", (_util.TOOLS / "mame" / "golden.lua").read_text())


if __name__ == "__main__":
    unittest.main()
