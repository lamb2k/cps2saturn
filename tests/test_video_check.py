import copy
import io
import json
import pathlib
import struct
import tempfile
import unittest
from contextlib import redirect_stdout

import _util  # noqa: F401
import cfg
import cps_video
import video_check

GAME = dict(layer_control=0x0A, priority=[0x0C, 0x0E, 0x00, 0x02], layer_enable_masks=[0x02, 0x04, 0x10])
SPRITES_ONLY = 0 << 6 | 1 << 8 | 2 << 10 | 3 << 12        # sprites bottom slot, every scroll layer off


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
GFX = tile(lambda x, y: 1 if x == 0 else 15) + tile(lambda x, y: 2)   # 0: left column pen 1; 1: solid pen 2


def sprites(obj, mapper=None):
    b = [0] * 32
    b[0x0A // 2] = SPRITES_ONLY
    f = cps_video.Frame(bytes(cps_video.GFX_RAM_SIZE), [0] * 32, b, GAME, GFX, mapper)
    return cps_video.render(f, obj)


DASH_CONFIG = """game:
  set: test
  board: cpsdash
paths:
  work: ""
cpu:
  irq_tap: [0x542, 0x543]
  irq_vector_pc: 0x68
ram:
  work_base: 0xff0000
  work_size: 0x10000
video:
  layer_control: 0x0a
  priority: [0x0c, 0x0e, 0x00, 0x02]
  layer_enable_masks: [0x16, 0x16, 0x16]
"""


class SpriteLayerTest(unittest.TestCase):
    def test_first_entry_is_on_top_and_pen_15_shows_through(self):
        pix = sprites(entry(64, 16, 0, 0x0003) + entry(64, 16, 1, 0x0001) + END)
        self.assertEqual(pix[0], 3 * 16 + 1)          # entry 0, bank 3, pen 1
        self.assertEqual(pix[1], 1 * 16 + 2)          # entry 1 shows through entry 0's pen 15
        self.assertEqual(pix[20], cps_video.BACKGROUND)

    def test_x_flip_mirrors_the_tile(self):
        pix = sprites(entry(64, 16, 0, 0x0020) + END)
        self.assertEqual((pix[15], pix[0]), (1, cps_video.BACKGROUND))

    def test_a_saturn_crop_in_the_config_does_not_move_the_reference_picture(self):
        b = [0] * 32
        b[0x0A // 2] = SPRITES_ONLY
        f = cps_video.Frame(bytes(cps_video.GFX_RAM_SIZE), [0] * 32, b, GAME, GFX, None)
        crop = dict(cps_video.cps_objects.CPS1_DEFAULT, view_x=80, view_w=352)
        self.assertEqual(cps_video.render(f, entry(64, 16, 1, 0x0001) + END, crop)[0], 1 * 16 + 2)

    def test_mapper_picks_the_tile(self):
        class M:
            def map(self, layer, code):
                return 1 if code == 7 else None
        self.assertEqual(sprites(entry(64, 16, 7, 0) + END, M())[5 * cps_video.W + 5], 2)


class CaptureTest(unittest.TestCase):
    def config(self, **video):
        c = copy.deepcopy(cfg.load(_util.EXAMPLE))
        c["game"]["board"] = "cpsdash"
        del c["ram"]["object_base"], c["ram"]["object_size"]
        c["video"] = dict(dict(layer_control=0x0A, priority=[0x0C, 0x0E, 0x00, 0x02],
                               layer_enable_masks=[0x16, 0x16, 0x16]), **video)
        return c

    def test_video_setup_is_required(self):
        c = self.config()
        del c["video"]["priority"]
        with self.assertRaises(SystemExit):
            video_check.game_video(c)

    def test_off_taps(self):
        c = self.config()
        self.assertEqual(video_check.off_taps(c, None), {})
        self.assertEqual(video_check.off_taps(c, "scrolls"), {"CPS2SAT_LAYER_CTRL": "0x80014a,0x16"})
        self.assertEqual(video_check.off_taps(c, "scroll2,scroll3"), {"CPS2SAT_VIDEO_CTRL": "0x800122,0xc"})
        with self.assertRaises(SystemExit):           # scroll1's mask is shared with layers that stay on
            video_check.off_taps(c, "scroll1")
        own = self.config(layer_enable_masks=[0x02, 0x04, 0x08], cps_b=0x800160)
        self.assertEqual(video_check.off_taps(own, "scroll1,scroll3"),
                         {"CPS2SAT_LAYER_CTRL": "0x80016a,0x2", "CPS2SAT_VIDEO_CTRL": "0x800122,0x8"})

    def test_dry_run_wraps_the_golden_run(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "c.yaml"
            text = _util.EXAMPLE.read_text().replace("board: cps2", "board: cpsdash")
            text = text.replace("  object_base: 0x708000\n  object_size: 0x2000\n", "")
            path.write_text(text + "\nvideo:\n  layer_control: 0x0a\n  priority: [0x0c, 0x0e, 0x00, 0x02]\n"
                                   "  layer_enable_masks: [0x16, 0x16, 0x16]\n")
            f = io.StringIO()
            with redirect_stdout(f):
                video_check.main(["capture", "--config", str(path), "--name", "x", "--frames", "5,3", "--last", "9",
                                  "--off", "scrolls", "--out-root", d, "--dry-run"])
            out = f.getvalue()
        self.assertIn("CPS2SAT_FRAMES=3,5", out)
        self.assertIn("CPS2SAT_OBJ_REG=0x800100,0x800", out)
        self.assertIn("CPS2SAT_GFX_RAM=0x900000,0x30000", out)
        self.assertIn("CPS2SAT_LAYER_CTRL=0x80014a,0x16", out)
        self.assertIn("video_frames.lua", out.splitlines()[-1])

    def test_frame_numbers_start_at_2(self):
        path = self.dash_config()
        with self.assertRaises(SystemExit):
            video_check.main(["capture", "--config", str(path), "--name", "x", "--frames", "1,5", "--last", "9",
                              "--dry-run"])
        f = io.StringIO()
        with redirect_stdout(f):
            self.assertEqual(video_check.main(["capture", "--config", str(path), "--name", "x", "--frames", "2",
                                               "--last", "9", "--out-root", self.tmp.name, "--dry-run"]), 0)
        self.assertIn("CPS2SAT_FRAMES=2", f.getvalue())

    def test_capture_refuses_a_cps2_config_before_starting_mame(self):
        with self.assertRaises(SystemExit) as e:
            video_check.main(["capture", "--config", str(_util.EXAMPLE), "--name", "x", "--frames", "5", "--last",
                              "9", "--dry-run"])
        self.assertIn("CPS-1", str(e.exception))

    def dash_config(self):
        if not hasattr(self, "tmp"):
            self.tmp = tempfile.TemporaryDirectory()
            self.addCleanup(self.tmp.cleanup)
        path = pathlib.Path(self.tmp.name) / "c.yaml"
        path.write_text(DASH_CONFIG)
        return path

    def test_frames_must_come_before_the_last_frame(self):
        with self.assertRaises(SystemExit):
            video_check.main(["capture", "--config", str(_util.EXAMPLE), "--name", "x", "--frames", "9", "--last",
                              "9", "--dry-run"])

    def test_lua_reads_the_names_the_tool_sets(self):
        lua = (_util.TOOLS / "mame" / "video_frames.lua").read_text()
        for name in ("CPS2SAT_GOLDEN_LUA", "CPS2SAT_LAYER_CTRL", "CPS2SAT_VIDEO_CTRL", "CPS2SAT_FRAMES",
                     "CPS2SAT_FRAMES_DIR", "CPS2SAT_GFX_RAM", "CPS2SAT_REG_SHARES", "CPS2SAT_GFX_OUT",
                     "CPS2SAT_GFX_REGION"):
            self.assertIn(f'"{name}"', lua)
        self.assertIn("cps2sat_golden_irq", (_util.TOOLS / "mame" / "golden.lua").read_text())


class CompareTest(unittest.TestCase):
    """compare() over a synthetic run folder, as video_frames.lua and golden.lua would leave it."""

    FRAME, IRQ = 5, 4                    # the picture of frame 5 uses record IRQ - 2 = 2 at offset 1

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run_dir = pathlib.Path(self.tmp.name) / "run"
        (self.run_dir / "frames").mkdir(parents=True)
        self.config = CaptureTest.dash_config(self)
        # One sprite (tile 1, solid pen 2, bank 1) at the picture origin; sprites in the bottom slot, scrolls off.
        objects = entry(64, 16, 1, 0x0001) + END
        obj = objects + bytes(0x800 - len(objects))
        with open(self.run_dir / "golden.bin", "wb") as f:
            for n in range(3):
                f.write(b"VBLK" + struct.pack(">I", n) + bytes(64) + bytes(0x10000) + (obj if n == 2 else bytes(0x800)))
        (self.run_dir / "gfx.bin").write_bytes(GFX)
        regs = [0] * 64
        regs[32 + 0x0A // 2] = SPRITES_ONLY
        self.pal = [((i * 7) & 0xFF) << 16 | ((i * 3) & 0xFF) << 8 | (i & 0xFF) for i in range(0xC00)]
        name = self.run_dir / "frames" / f"f{self.FRAME:05d}"
        name.with_suffix(".regs").write_bytes(struct.pack(">64H", *regs))
        name.with_suffix(".gfx").write_bytes(bytes(cps_video.GFX_RAM_SIZE))
        name.with_suffix(".pal").write_bytes(struct.pack(f">{len(self.pal)}I", *self.pal))
        b = [0] * 32
        b[0x0A // 2] = SPRITES_ONLY
        pix = cps_video.render(cps_video.Frame(bytes(cps_video.GFX_RAM_SIZE), [0] * 32, b, GAME, GFX, None), objects)
        self.rgb = bytearray(b"".join(struct.pack("<I", 0xFF000000 | self.pal[i]) for i in pix))
        self.write(frames=[self.FRAME], log=[self.FRAME])

    def write(self, frames, log):
        (self.run_dir / "manifest.json").write_text(json.dumps(dict(frames=frames, delta=False)))
        (self.run_dir / "frames" / "frames.txt").write_text(
            "byteorder le\n" + "".join(f"{f} {self.IRQ} 384 224\n" for f in log))
        (self.run_dir / "frames" / f"f{self.FRAME:05d}.rgb").write_bytes(bytes(self.rgb))

    def compare(self):
        f = io.StringIO()
        with redirect_stdout(f):
            rc = video_check.main(["compare", str(self.run_dir), "--config", str(self.config), "--offset", "1"])
        return rc, f.getvalue()

    def test_a_complete_matching_run_passes(self):
        rc, out = self.compare()
        self.assertEqual(rc, 0, out)
        self.assertIn("1 of 1 frames pass", out)

    def test_one_wrong_pixel_fails(self):
        self.rgb[0] ^= 0x01
        self.write(frames=[self.FRAME], log=[self.FRAME])
        rc, out = self.compare()
        self.assertEqual(rc, 1)
        self.assertIn("1 px differ", out)

    def test_an_empty_capture_fails(self):
        self.write(frames=[self.FRAME, 7], log=[])
        rc, out = self.compare()
        self.assertEqual(rc, 1)
        self.assertIn("incomplete capture", out)

    def test_a_partial_capture_fails(self):
        self.write(frames=[self.FRAME, 7], log=[self.FRAME])          # frame 7 asked for, never written
        rc, out = self.compare()
        self.assertEqual(rc, 1)
        self.assertIn("frame 7 is not in frames.txt", out)
        self.write(frames=[self.FRAME], log=[self.FRAME])
        (self.run_dir / "frames" / f"f{self.FRAME:05d}.gfx").unlink()   # a file of a logged frame missing
        rc, out = self.compare()
        self.assertEqual(rc, 1)
        self.assertIn("f00005.gfx is missing", out)

    def test_no_requested_frames_fails(self):
        self.write(frames=[], log=[])
        rc, out = self.compare()
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
