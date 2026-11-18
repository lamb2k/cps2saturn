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


if __name__ == "__main__":
    unittest.main()
