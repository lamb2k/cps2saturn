import copy
import json
import pathlib
import tempfile
import unittest

import _util  # noqa: F401
import vdp2_cycle_check as chk

# Word order: A0L, A0U, A1L, A1U, B0L, B0U, B1L, B1U. One nibble per timing, T0 first.
# Layers NBG0-2, 16 colours at 1x. Names in B1 at T0/T1/T2, cells in A0 at T4/T5/T6,
# CPU slot T3 in A0+A1 and T7 in B0+B1, each with a no-access slot in front.
GOOD = ["0xFFFE", "0x456F", "0xFFFE", "0xFFFF", "0xFFFF", "0xFFFE", "0x012F", "0xFFFE"]
SPEC = {
    "ramctl": 0x1300,
    "cycles": GOOD,
    "layers": {
        "nbg0": {"colours": 16, "reduction": 1, "map_banks": ["B1"], "cell_banks": ["A0"]},
        "nbg1": {"colours": 16, "reduction": 1, "map_banks": ["B1"], "cell_banks": ["A0"]},
        "nbg2": {"colours": 16, "reduction": 1, "map_banks": ["B1"], "cell_banks": ["A0"]},
    },
}
# One layer at 1/2 reduction needs 2 name reads and 2 cell reads (2+2).
REDUCED_GOOD = ["0xFFFE", "0x44FF", "0xFFFE", "0xFFFF", "0xFFFF", "0xFFFE", "0x00FF", "0xFFFE"]
REDUCED_SPEC = {
    "ramctl": 0x1300,
    "cycles": REDUCED_GOOD,
    "layers": {"nbg0": {"colours": 16, "reduction": 2, "map_banks": ["B1"], "cell_banks": ["A0"]}},
}


def run(spec, words=None):
    return chk.check_spec(spec, words)[0]


def with_cycles(spec, **edits):
    s = copy.deepcopy(spec)
    s["cycles"] = list(s["cycles"])
    for idx, val in edits.items():
        s["cycles"][int(idx[1:])] = val
    return s


class CycleWordsTest(unittest.TestCase):
    def test_known_good(self):
        self.assertEqual(run(SPEC), [])
        self.assertEqual(run(REDUCED_SPEC), [])

    def test_reduced_layer_needs_two_and_two(self):
        s = copy.deepcopy(REDUCED_SPEC)
        s["cycles"] = ["0xFFFE", "0x4FFF", "0xFFFE", "0xFFFF", "0xFFFF", "0xFFFE", "0x0FFF", "0xFFFE"]
        errs = run(s)
        self.assertTrue(any("1 pattern name read" in e and "needs 2" in e for e in errs), errs)
        self.assertTrue(any("1 cell read" in e and "needs 2" in e for e in errs), errs)

    def test_missing_cell_read(self):
        errs = run(with_cycles(SPEC, w1="0x45FF"))   # NBG2 loses its cell read
        self.assertTrue(any("NBG2 has 0 cell read" in e for e in errs), errs)

    def test_cell_timing_not_legal_for_name_timing(self):
        # NBG1 name at T1, cell moved to T4: not in the legal set for a T1 name read.
        errs = run(with_cycles(SPEC, w1="0x546F"))
        self.assertTrue(any("NBG1 cell read at T4 is not allowed with a name read at T1" in e for e in errs), errs)

    def test_cpu_slot_in_one_bank_only(self):
        errs = run(with_cycles(SPEC, w2="0xFFFF"))   # A1 lost its CPU slot, A0 still has one
        self.assertTrue(any("only one of A0/A1" in e for e in errs), errs)

    def test_cpu_run_without_no_access_in_front(self):
        errs = run(with_cycles(SPEC, w0="0xFF6E", w1="0x45FF"))   # A0 slot 2 is a read, not no-access
        self.assertTrue(any("not preceded by no access" in e for e in errs), errs)

    def test_colour_depth_not_allowed_at_reduction(self):
        s = copy.deepcopy(REDUCED_SPEC)
        s["layers"]["nbg0"]["colours"] = 16777216
        self.assertTrue(any("not allowed" in e for e in run(s)))

    def test_names_in_both_a0_and_b0(self):
        # NBG0 names in A0 at T0, NBG1 names in B0 at T1: both on the same side of the split.
        s = {"ramctl": 0x1300,
             "cycles": ["0x0FFE", "0x45FF", "0xFFFE", "0xFFFF", "0xF1FF", "0xFFFE", "0xFFFF", "0xFFFE"],
             "layers": {"nbg0": {"colours": 16, "map_banks": ["A0"], "cell_banks": ["A0"]},
                        "nbg1": {"colours": 16, "map_banks": ["B0"], "cell_banks": ["A0"]}}}
        errs = run(s)
        self.assertEqual(len(errs), 1, errs)
        self.assertIn("only one of A0/B0 and one of A1/B1", errs[0])
        # Same pattern with NBG1's names in B1 (and its map there) is legal.
        s["cycles"][4:8] = ["0xFFFF", "0xFFFE", "0xF1FF", "0xFFFE"]
        s["layers"]["nbg1"]["map_banks"] = ["B1"]
        self.assertEqual(run(s), [])

    def test_bad_input(self):
        with self.assertRaises(chk.BadInput):
            chk.words_to_codes([0] * 7)
        with self.assertRaises(chk.BadInput):
            chk.check_spec({"cycles": GOOD, "layers": {"nbg0": {"colours": 7}}})


class TraceTest(unittest.TestCase):
    # Register writes that set up the GOOD pattern: display on, NBG0-2 on, 16 colours, one-word names,
    # maps in B1 (0x60000 / 0x2000 per page = 0x30..0x32), then the cycle words.
    SETUP = [("00", "8000"), ("0e", "1300"), ("20", "0007"), ("28", "0000"), ("2a", "0000"),
             ("30", "8000"), ("32", "8000"), ("34", "8000"), ("3a", "0000"),
             ("40", "3030"), ("42", "3030"), ("44", "3131"), ("46", "3131"), ("48", "3232"), ("4a", "3232")]

    def lines(self, cycles):
        out = ["# synthetic trace"]
        out += [f"{i} W16 25F800{o} {v}" for i, (o, v) in enumerate(self.SETUP)]
        out += [f"{100 + i} W16 25F800{o:02X} {w[2:]}" for i, (o, w) in enumerate(zip(chk.CYC_OFFSETS, cycles))]
        out.append("tick vblank")   # a non-register line ends the burst
        return out

    def test_good_and_bad_states(self):
        spec = {"require_ramctl": 0x1300, "layers": {"nbg0": {"cell_banks": ["A0"]}, "nbg1": {"cell_banks": ["A0"]},
                                                       "nbg2": {"cell_banks": ["A0"]}}}
        bursts, states = chk.check_trace(self.lines(GOOD), spec)
        self.assertEqual(bursts, 1)
        self.assertFalse(any(v[0] for v in states.values()), states)
        bad = list(GOOD)
        bad[1] = "0x546F"
        bursts, states = chk.check_trace(self.lines(GOOD) + self.lines(bad), spec)
        self.assertEqual(len([v for v in states.values() if v[0]]), 1)

    def test_display_off_is_not_judged(self):
        lines = [l for l in self.lines(["0x0000"] * 8) if "25F80000 8000" not in l]
        bursts, _ = chk.check_trace(lines, {})
        self.assertEqual(bursts, 0)


class ZoomIncrementTest(unittest.TestCase):
    """ZMXIN/ZMXDN/ZMYIN/ZMYDN of an enabled NBG0 or NBG1: 0 is an error, the reset value 1.0 is not."""
    SETUP = TraceTest.SETUP

    def regs(self, **zoom):
        r = {int(o, 16): int(v, 16) for o, v in self.SETUP}
        r.update({o: int(w, 16) for o, w in zip(chk.CYC_OFFSETS, GOOD)})
        r.update({int(k[1:], 16): v for k, v in zoom.items()})   # keys like r78 = value
        return r

    def errs(self, regs):
        spec = {"layers": {"nbg0": {"cell_banks": ["A0"]}, "nbg1": {"cell_banks": ["A0"]}, "nbg2": {"cell_banks": ["A0"]}}}
        return chk.judge_regs(regs, spec)[0]

    def test_registers_never_written_keep_the_reset_value(self):
        self.assertEqual(self.errs(self.regs()), [])

    def test_one_to_one_written(self):
        self.assertEqual(self.errs(self.regs(r78=1, r7a=0, r7c=1, r7e=0, r88=1, r8a=0, r8c=1, r8e=0)), [])

    def test_a_zero_fill_is_an_error_per_register_and_layer(self):
        e = self.errs(self.regs(r78=0, r7a=0, r7c=0, r7e=0, r88=0, r8a=0, r8c=0, r8e=0))
        self.assertEqual(len(e), 4, e)
        self.assertTrue(any("NBG0 horizontal" in x and "ZMXIN0" in x for x in e), e)
        self.assertTrue(any("NBG0 vertical" in x for x in e), e)
        self.assertTrue(any("NBG1 horizontal" in x for x in e), e)
        self.assertTrue(any("NBG1 vertical" in x for x in e), e)

    def test_only_the_horizontal_increment_of_nbg1(self):
        e = self.errs(self.regs(r88=0, r8a=0))
        self.assertEqual(len(e), 1, e)
        self.assertIn("NBG1 horizontal", e[0])

    def test_a_fraction_alone_is_not_zero(self):
        self.assertEqual(self.errs(self.regs(r78=0, r7a=0x8000)), [])   # 0.5

    def test_a_layer_that_is_off_is_not_judged_and_nbg2_has_no_increments(self):
        r = self.regs(r78=0, r7c=0, r88=0, r8c=0)
        r[chk.BGON] = 0x0004
        self.assertEqual(self.errs(r), [])

    def test_trace_replay_fails_on_a_zero_fill_and_passes_once_one_is_written(self):
        spec = {"require_ramctl": 0x1300, "layers": {"nbg0": {"cell_banks": ["A0"]}, "nbg1": {"cell_banks": ["A0"]}, "nbg2": {"cell_banks": ["A0"]}}}
        base = TraceTest().lines(GOOD)[:-1]
        zero = [f"{200 + i} W16 25F800{o:02X} 0000" for i, o in enumerate(chk.ZOOM_REGS)]
        fix = ["300 W16 25F80078 0001", "301 W16 25F8007C 0001", "302 W16 25F80088 0001", "303 W16 25F8008C 0001"]
        bursts, states = chk.check_trace(base + zero + ["tick vblank"], spec)
        bad = [v for v in states.values() if v[0]]
        self.assertEqual(len(bad), 1)
        self.assertIn("coordinate increment", bad[0][0][0])
        bursts, states = chk.check_trace(base + zero + fix + ["tick vblank"], spec)
        self.assertFalse(any(v[0] for v in states.values()), states)

    def test_trace_keys_cover_the_increments(self):
        for o in range(0x78, 0x90, 2):
            self.assertIn(o, chk.TRACE_KEYS)


class CliTest(unittest.TestCase):
    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "good.json").write_text(json.dumps(SPEC))
            bad = with_cycles(SPEC, w2="0xFFFF")
            (d / "bad.json").write_text(json.dumps(bad))
            (d / "junk.json").write_text("{not json")
            self.assertEqual(chk.main([str(d / "good.json"), "--quiet"]), 0)
            self.assertEqual(chk.main([str(d / "bad.json"), "--quiet"]), 1)
            self.assertEqual(chk.main([str(d / "junk.json")]), 2)
            self.assertEqual(chk.main([str(d / "missing.json")]), 2)
            # --cyc replaces the spec's words
            self.assertEqual(chk.main([str(d / "good.json"), "--quiet", "--cyc", "FFFE,456F,FFFF,FFFF,FFFF,FFFE,012F,FFFE"]), 1)


if __name__ == "__main__":
    unittest.main()
