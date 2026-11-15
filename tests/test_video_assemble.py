import json
import pathlib
import tempfile
import unittest

import _util  # noqa: F401

_util.sys.path.insert(0, str(_util.TOOLS / "video"))
import assemble  # noqa: E402  (imports without Pillow)

try:
    from PIL import Image
    HAVE = True
except ImportError:
    HAVE = False


def make_frames(folder: pathlib.Path, n: int, frame=(96, 72), box=(8, 6, 80, 60)):
    """Synthetic capture: a 4:3 picture of moving colour bars inside a black frame."""
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        im = Image.new("RGB", frame, "#000000")
        pic = Image.new("RGB", (box[2], box[3]), (40 + i * 6 % 200, 120, 200 - i * 5 % 150))
        for x in range(0, box[2], 10):
            pic.paste((255, 255, 255), (x + i % 5, 0, x + i % 5 + 3, box[3]))
        im.paste(pic, (box[0], box[1]))
        im.save(folder / ("f%06d.png" % i))


def edl(tmp: pathlib.Path, **extra):
    e = dict(title="t", out=str(tmp / "out"), fps=30, size=[320, 180], frames=30, shots_root=str(tmp / "shots"),
             crop=[8, 6, 80, 60], loop_bridge=4, exports=["web30"],
             captions=[dict(text="Test caption", at=2, dur=20, pos="bottom", size=60)],
             tags=[dict(text="Emulator capture", pos="br")],
             clips=[dict(id="a", at=0, dur=14, src="a", layout="pillar"),
                    dict(id="b", at=14, dur=10, src="a", layout="punch", punch=dict({"from": [0.5, 0.5, 1.0], "to": [0.3, 0.4, 2.0]}),
                         fade_in=2),
                    dict(id="card", at=24, dur=6, card=dict(bg="#101030", lines=[dict(text="End", y=0.4, size=80)]), fade_out=2)])
    e.update(extra)
    return e


class AssembleNoDepsTest(unittest.TestCase):
    def test_presets_are_generic_and_known(self):
        self.assertIn("web60", assemble.EXPORT_PRESETS)
        names = " ".join(assemble.EXPORT_PRESETS) + " " + " ".join(p["suffix"] for p in assemble.EXPORT_PRESETS.values())
        for site in ("reddit", "twitter", "x_"):
            self.assertNotIn(site, names.lower())
        with self.assertRaises(SystemExit):
            assemble.resolve_exports({"exports": ["nope"]})
        self.assertEqual(list(assemble.resolve_exports({"exports": ["web30"]})), ["web30"])
        custom = assemble.resolve_exports({"exports": ["mine"], "export_presets": {"mine": dict(suffix="m", bitrate="1M", maxrate="1M", bufsize="1M")}})
        self.assertIn("mine", custom)

    def test_no_windows_font_paths(self):
        text = (_util.TOOLS / "video" / "assemble.py").read_text(encoding="utf-8")
        self.assertNotIn("Windows/Fonts", text)
        self.assertNotIn("reveal", text.lower())

    def test_font_from_edit_list_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / "x.ttf"
            f.write_bytes(b"not a real font")
            self.assertEqual(assemble.find_font(str(f)), str(f))

    def test_audio_graph(self):
        ins, graph = assemble.audio_args(dict(audio=[dict(file="m.raw", at=0, cdda=True, gain_db=-6), dict(file="v.wav", at=60)]), 60, 5)
        self.assertIn("-f", ins)
        self.assertIn("amix=inputs=2", graph)
        self.assertIn("adelay=1000|1000", graph)
        self.assertEqual(assemble.audio_args({}, 60, 5), ([], None))
        _i, g2 = assemble.audio_args(dict(audio_mix="mix.wav"), 60, 5)
        self.assertNotIn("alimiter", g2)

    def test_usage_without_arguments(self):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(assemble.main([]), 2)


@unittest.skipUnless(HAVE, "Pillow not installed")
class AssemblePillowTest(unittest.TestCase):
    def test_probe_finds_the_picture_box(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_frames(pathlib.Path(tmp) / "a", 6)
            box, size, n = assemble.probe_box(pathlib.Path(tmp) / "a")
            self.assertEqual(box, [8, 6, 80, 60])
            self.assertEqual((size, n), ((96, 72), 6))

    def test_smoothness_counts_distinct_pictures(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp) / "a"
            make_frames(d, 10)
            s = assemble.smoothness(d)
            self.assertEqual(s["frames"], 10)
            self.assertEqual(s["distinct_per_60"], 60.0)

    def test_sheet_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            make_frames(tmp / "shots" / "a", 20)
            rep = assemble.render(edl(tmp), sheet_only=True)
            self.assertEqual(rep["problems"], [])
            self.assertTrue((tmp / "out" / "t_sheet.png").exists())
            self.assertEqual(len(rep["clips"]), 3)

    def test_problems_are_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            make_frames(tmp / "shots" / "a", 5)
            e = edl(tmp, standin=str(tmp / "shots" / "a"))
            e["clips"].append(dict(id="late", at=26, dur=4, src="missing"))
            e["clips"][0]["dur"] = 10      # leaves a gap
            rep = assemble.render(e, sheet_only=True)
            text = " ".join(rep["problems"])
            self.assertIn("stand-in", text)
            self.assertIn("no clip", text)
            self.assertIn("source frames", text)

    def test_full_render_with_a_loop_and_a_web_export(self):
        try:
            import subprocess
            subprocess.run([assemble.FFMPEG, "-version"], capture_output=True, check=True)
        except Exception:
            self.skipTest("ffmpeg not available")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            make_frames(tmp / "shots" / "a", 20)
            rep = assemble.render(edl(tmp))
            self.assertIn("master", rep["outputs"])
            self.assertIn("web30", rep["outputs"])
            for v in rep["outputs"].values():
                self.assertGreater(pathlib.Path(v["path"]).stat().st_size, 1000)
            self.assertIn("loop_seam_mean_abs_diff", rep)
            self.assertTrue((tmp / "out" / "t_poster.png").exists())
            self.assertEqual(json.loads((tmp / "out" / "t_report.json").read_text())["frames"], 30)


if __name__ == "__main__":
    unittest.main()
