"""The VDP2 writer scan in tools/vdp2_cycle_check.py (--scan-writers): synthetic C sources, the allowlist, and the kit's own saturn/ tree."""
import io
import contextlib
import pathlib
import tempfile
import unittest

import _util  # noqa: F401
import vdp2_cycle_check as chk

ROOT = pathlib.Path(__file__).resolve().parents[1]

GAME = """\
void layers(void)
{
    SAT_VDP2_REG(0x10) = SAT_V2_CYC_HALF_A0L;      /* from the layout */
    SAT_VDP2_REG(0x12) = 0x67fe;                   /* a literal: a second writer */
    sat_v2l_write(&latch, 0x28, SAT_V2_CHCTLA);    /* the latch form, from the layout */
    sat_v2l_write(&latch, 0x2a, 0x1111);           /* the latch form, a literal */
    SAT_VDP2_REG(0x00) = 0x8000;                   /* TVMD: not a covered register */
    SAT_VDP2_REG(0x14) = 0xffff; /* SAT_V2_ in a comment must not count */
    // SAT_VDP2_REG(0x16) = 0x1234;  commented out, not a write
}
"""
DIAG = """\
void diag(void)
{
    SAT_VDP2_REG(0x98) = 0x0101;
#ifdef GAME_CYC_DIAG
    SAT_VDP2_REG(0x0e) = 0x1300;
#endif
    SAT_VDP2_REG(0x0e) = 0x0300;
}
"""


class WriterScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        (self.root / "rt").mkdir()
        (self.root / "rt" / "game.c").write_text(GAME)
        (self.root / "rt" / "diag.c").write_text(DIAG)
        (self.root / "rt" / "notes.txt").write_text("SAT_VDP2_REG(0x10) = 1;")   # not a C source

    def tearDown(self):
        self.tmp.cleanup()

    def allow(self, text):
        p = self.root / "allow.txt"
        p.write_text(text)
        return chk.load_writer_allow(str(p))

    def test_unreviewed_literals_are_found_and_macros_pass(self):
        problems, seen, stale = chk.scan_writers(self.root, [])
        text = "\n".join(problems)
        self.assertIn("rt/game.c:4: write of VDP2 0x012 = 0x67fe", text)
        self.assertIn("rt/game.c:6: write of VDP2 0x02a = 0x1111", text)
        self.assertIn("rt/game.c:8: write of VDP2 0x014 = 0xffff", text)   # a macro name in a comment does not make the value one
        self.assertNotIn("VDP2 0x010 ", text)                                    # from the layout
        self.assertNotIn("VDP2 0x028 ", text)
        self.assertNotIn("VDP2 0x000 ", text)                                    # TVMD is not covered
        self.assertNotIn("VDP2 0x016 ", text)                                    # commented out
        self.assertIn("rt/diag.c:3: write of VDP2 0x098", text)
        self.assertEqual(len(problems), 6)                                 # game: 3, diag: 0x98, 0x0e twice
        self.assertEqual(seen, 8)
        self.assertEqual(stale, [])

    def test_ifdef_blocks_of_a_build_that_never_ships_are_skipped(self):
        problems, seen, _ = chk.scan_writers(self.root, [], skip_ifdefs=("GAME_CYC_DIAG",))
        self.assertEqual(len(problems), 5)
        self.assertEqual(seen, 7)
        self.assertFalse(any("0x1300" in p for p in problems))

    def test_allowlist_clears_a_line_and_reports_stale_entries(self):
        allow = self.allow("# reviewed\n"
                           "rt/diag.c | SAT_VDP2_REG(0x98) = 0x0101 | boot display: no layer enabled\n"
                           "rt/diag.c | 0x0e) = 0x0300 | stop screen: own mode\n"
                           "rt/diag.c | 0x0e) = 0x1300 | the cycle diagnostic (also skipped, so the entry is not needed)\n"
                           "rt/gone.c | SAT_VDP2_REG(0x10) | file removed\n")
        problems, _, stale = chk.scan_writers(self.root, allow)
        self.assertFalse(any(p.startswith("rt/diag.c:3") for p in problems))
        self.assertEqual(sum(p.startswith("rt/diag.c") for p in problems), 0)   # 0x1300 matched by its own entry too
        self.assertEqual(len(problems), 3)                                      # the game's three literals
        self.assertEqual(stale, ["rt/gone.c | SAT_VDP2_REG(0x10) | file removed"])

    def test_other_writer_names_and_ok_patterns(self):
        (self.root / "rt" / "other.c").write_text("void f(void) { V2R(0x10) = LAYOUT_A0L; V2R(0x12) = 5; }\n")
        problems, seen, _ = chk.scan_writers(self.root, [], writers=("V2R",), ok_pattern=r"\bLAYOUT_\w+")
        self.assertEqual((len(problems), seen), (1, 2))
        self.assertIn("rt/other.c:1: write of VDP2 0x012 = 5", problems[0])

    def test_allowlist_needs_all_three_parts(self):
        for text in ("rt/diag.c | 0x98\n", "rt/diag.c |  | reason\n", "just words\n"):
            with self.assertRaises(chk.BadInput):
                self.allow(text)

    def test_not_a_folder_is_bad_input(self):
        with self.assertRaises(chk.BadInput):
            chk.scan_writers(self.root / "missing", [])

    def test_cli_exit_codes(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(chk.main(["--scan-writers", str(self.root)]), 1)
            self.assertEqual(chk.main(["--scan-writers", str(self.root / "rt" / "diag.c")]), 2)
            (self.root / "ok").mkdir()
            (self.root / "ok" / "a.c").write_text("void f(void) { SAT_VDP2_REG(0x10) = SAT_V2_CYC_X; }\n")
            self.assertEqual(chk.main(["--scan-writers", str(self.root / "ok")]), 0)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(chk.main([]), 2)   # neither a spec nor a scan

    def test_scan_and_spec_both_judge(self):
        import json
        good = {"ramctl": 0x1300, "cycles": ["0xFFFE", "0x456F", "0xFFFE", "0xFFFF", "0xFFFF", "0xFFFE", "0x012F", "0xFFFE"],
                "layers": {"nbg0": {"colours": 16, "reduction": 1, "map_banks": ["B1"], "cell_banks": ["A0"]}}}
        (self.root / "good.json").write_text(json.dumps(good))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(chk.main([str(self.root / "good.json"), "--quiet"]), 0)
            self.assertEqual(chk.main([str(self.root / "good.json"), "--quiet", "--scan-writers", str(self.root / "rt")]), 1)   # the spec passes, the writers do not

    def test_the_kits_own_saturn_tree_has_no_unreviewed_writers(self):
        problems, _, _ = chk.scan_writers(ROOT / "saturn", [])
        self.assertEqual(problems, [])


GOOD_SPEC = {"ramctl": 0x1300, "cycles": ["0xFFFE", "0x456F", "0xFFFE", "0xFFFF", "0xFFFF", "0xFFFE", "0x012F", "0xFFFE"],
             "layers": {"nbg0": {"colours": 16, "reduction": 1, "map_banks": ["B1"], "cell_banks": ["A0"]},
                        "nbg1": {"colours": 16, "reduction": 1, "map_banks": ["B1"], "cell_banks": ["A0"]},
                        "nbg2": {"colours": 16, "reduction": 1, "map_banks": ["B1"], "cell_banks": ["A0"]}}}

BGON_SRC = """void screens(void)
{
    SAT_VDP2_REG(0x20) = 0x0007;                  /* NBG0 to NBG2: all have reads */
    SAT_VDP2_REG(0x20) = 0x0008;                  /* NBG3: not described by the spec, no reads */
    SAT_VDP2_REG(0x20) = SAT_V2_BGON_GAME;        /* from the layout: not judged here */
    SAT_VDP2_REG(0x20) = bgon | 1;                /* not a plain literal */
}
"""
ZOOM_ZERO = """void clear(void)
{
    SAT_VDP2_REG(0x78) = 0;                       /* ZMXIN0 */
    SAT_VDP2_REG(0x7c) = 0x0000;
    SAT_VDP2_REG(0x88) = SAT_V2_ZOOM_ONE;
    SAT_VDP2_REG(0x8c) = 1;
}
"""


class BgonAndZoomScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, name, text):
        (self.root / name).write_text(text)

    def test_the_new_registers_are_watched(self):
        for o in (0x20, 0x78, 0x7a, 0x7c, 0x7e, 0x88, 0x8a, 0x8c, 0x8e, 0xac, 0xae):
            self.assertIn(o, chk.WATCH)

    def test_literal_bgon_is_judged_against_the_specs_cycle_words(self):
        self.put("s.c", BGON_SRC)
        problems, seen, _ = chk.scan_writers(self.root, [], spec=GOOD_SPEC)
        self.assertEqual(seen, 4)
        self.assertTrue(any(p.startswith("s.c:4: write of VDP2 0x020 = 0x0008") for p in problems), problems)   # a literal is also a second writer
        self.assertTrue(any(p.startswith("s.c:4: BGON = 0x0008") and "nbg3" in p for p in problems), problems)   # NBG3 is not in the spec
        self.assertFalse(any(p.startswith("s.c:3: BGON") for p in problems), problems)                         # 0x0007 has its reads
        self.assertFalse(any(p.startswith("s.c:5: BGON") or p.startswith("s.c:6: BGON") for p in problems), problems)   # macro and expression: not judged

    def test_bgon_value_that_enables_a_layer_without_reads(self):
        words = list(GOOD_SPEC["cycles"])
        words[1] = "0x45FF"   # NBG2 loses its cell read
        spec = dict(GOOD_SPEC, cycles=words)
        self.put("s.c", "void f(void) { SAT_VDP2_REG(0x20) = 0x0007; }\n")
        problems, _, _ = chk.scan_writers(self.root, [], spec=spec)
        self.assertTrue(any("BGON = 0x0007" in p and "NBG2 has 0 cell read" in p for p in problems), problems)
        problems, _, _ = chk.scan_writers(self.root, [])   # without a spec only the macro rule applies
        self.assertEqual(len(problems), 1)

    def test_allowlisted_bgon_is_not_judged(self):
        self.put("s.c", BGON_SRC)
        allow = [("s.c", "= 0x0008;", "stop screen: own display set-up")]
        problems, _, stale = chk.scan_writers(self.root, allow, spec=GOOD_SPEC)
        self.assertFalse(any(p.startswith("s.c:4") for p in problems), problems)
        self.assertEqual(stale, [])

    def test_zoom_register_only_ever_written_zero_is_an_error(self):
        self.put("z.c", ZOOM_ZERO)
        problems, _, _, _ = chk.scan_writers_ex(self.root, [])
        text = "\n".join(problems)
        self.assertIn("ZMXIN0 (offset 0x78) is only ever written 0", text)
        self.assertIn("ZMYIN0 (offset 0x7c) is only ever written 0", text)
        self.assertNotIn("ZMXIN1 (offset", text)   # written from a macro
        self.assertNotIn("ZMYIN1 (offset", text)   # written 1 (not from a macro: that is the macro rule's finding)
        self.assertTrue(any("write of VDP2 0x08c = 1 is not from a layout macro" in p for p in problems), problems)

    def test_zoom_written_zero_then_non_zero_passes_the_zoom_rule(self):
        self.put("z.c", "void f(void) { SAT_VDP2_REG(0x78) = 0; SAT_VDP2_REG(0x78) = SAT_V2_ONE; SAT_VDP2_REG(0x7c) = SAT_V2_ONE;"
                        " SAT_VDP2_REG(0x88) = SAT_V2_ONE; SAT_VDP2_REG(0x8c) = SAT_V2_ONE; }\n")
        problems, _, _, _ = chk.scan_writers_ex(self.root, [])
        self.assertFalse(any("only ever written 0" in p for p in problems), problems)

    def test_no_zoom_write_is_a_note_and_an_error_with_require_zoom(self):
        self.put("a.c", "void f(void) { SAT_VDP2_REG(0x10) = SAT_V2_CYC_X; }\n")
        problems, _, _, info = chk.scan_writers_ex(self.root, [])
        self.assertEqual(problems, [])
        self.assertEqual(len([i for i in info if "no recognised write sets ZM" in i]), 4, info)
        problems, _, _, _ = chk.scan_writers_ex(self.root, [], require_zoom=True)
        self.assertEqual(len(problems), 4, problems)

    def test_cli_with_a_spec_and_require_zoom(self):
        import json
        (self.root / "spec.json").write_text(json.dumps(GOOD_SPEC))
        src = self.root / "src"
        src.mkdir()
        (src / "a.c").write_text("void f(void) { SAT_VDP2_REG(0x20) = SAT_V2_BGON_X; }\n")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(chk.main(["--scan-writers", str(src)]), 0)
            self.assertEqual(chk.main(["--scan-writers", str(src), "--require-zoom"]), 1)
            self.assertEqual(chk.main([str(self.root / "spec.json"), "--scan-writers", str(src)]), 0)
            (src / "b.c").write_text("void f(void) { SAT_VDP2_REG(0x20) = 0x0008; }\n")
            self.assertEqual(chk.main([str(self.root / "spec.json"), "--scan-writers", str(src)]), 1)


if __name__ == "__main__":
    unittest.main()
