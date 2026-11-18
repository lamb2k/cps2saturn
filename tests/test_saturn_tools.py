"""Tests of the saturn/ kit pieces that need no C compiler: the placement tools, the OPX store, the VDP2 patterns against the cycle checker,
the module list in saturn/README.md, and the SH-2 build check (skipped without a cross compiler)."""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import _util  # noqa: F401
import fn_heat
import opx_store
import place_plan
import saturn_build_check
import vdp2_cycle_check as chk

ROOT = pathlib.Path(__file__).resolve().parents[1]
SATURN = ROOT / "saturn"

MAP = """\
 .text          0x06014000      0x400 c0.o
 .text.f_hot    0x06014400      0x80 obj/c1.o
 .text.long_section_name_that_wraps_the_line
                0x06014480      0x40 obj/c1.o
 .text          0x060144c0        0x0 empty.o
"""
NM = """\
06014000 00000100 T _f_a
06014100 00000200 T _f_b
06014400 00000080 T _g_hot
06014480 00000040 t _g_cold
06014480 00000040 T _g_cold_alias
"""
PROFILE = """\
P 0 06014010 1000
P 0 06014020 500
IF 0 06014010 7
P 1 06014010 999999
P 2 06014420 50
P 0 00000100 77
P 0 05c00000 77
P 0 06014490 3
junk line
"""


class FnHeatTest(unittest.TestCase):
    def test_object_ranges_and_wrapped_names(self):
        rng = fn_heat.object_ranges(MAP)
        self.assertEqual([(r[0], r[1], r[2]) for r in rng], [(0x6014000, 0x6014400, "c0"), (0x6014400, 0x6014480, "c1"), (0x6014480, 0x60144c0, "c1")])

    def test_heat_counts_only_the_wanted_classes_and_addresses(self):
        rng = fn_heat.object_ranges(MAP)
        syms = fn_heat.parse_nm(NM)
        heat = fn_heat.compute_heat([PROFILE], rng, syms)
        self.assertEqual(heat["c0:f_a"]["exec"], 1500)       # class 1 left out
        self.assertEqual(heat["c0:f_a"]["ifill"], 7)
        self.assertEqual(heat["c0:f_a"]["size"], 0x100)
        self.assertEqual(heat["c1:g_hot"]["exec"], 50)       # class 2 counted
        self.assertEqual(heat["c1:g_cold"]["exec"], 3)       # symbols sharing an address all get the heat
        self.assertEqual(heat["c1:g_cold_alias"]["exec"], 3)
        self.assertNotIn("c0:f_b", heat)                     # never ran
        self.assertEqual(len(heat), 4)                       # addresses below the window and in the VDP range are ignored


class PlacePlanTest(unittest.TestCase):
    FUNCS = [{"key": f"o:f{i}", "size": 100, "region": r} for i, r in enumerate(["hw", "hw", "hw", "lw", "lw", "cart"])]

    def kept(self, promote, demote):
        k = {f["key"] for f in self.FUNCS if f["region"] == "hw"} - {x["key"] for l in demote.values() for x in l}
        return k | {x["key"] for l in promote.values() for x in l}

    def test_hot_code_moves_in_and_cold_code_moves_out_within_the_budget(self):
        heat = {"o:f0": {"exec": 10, "ifill": 0}, "o:f3": {"exec": 100000, "ifill": 10}, "o:f5": {"exec": 5000, "ifill": 0}}
        promote, demote, rep = place_plan.plan(heat, self.FUNCS, "hw", 200, spare={"lw": 1000})
        kept = self.kept(promote, demote)
        self.assertEqual(kept, {"o:f0", "o:f3"})              # f0 ran and was already fast: stays; f3 is the hottest outsider; f5 has no room
        self.assertEqual(rep["fast_code_kept"], 200)
        self.assertEqual(rep["bytes_without_room"], 0)
        self.assertEqual({x["key"] for x in demote["lw"]}, {"o:f1", "o:f2"})   # the cold fast-region code goes to low RAM

    def test_code_that_cannot_leave_stays_and_is_reported(self):
        heat = {"o:f0": {"exec": 10, "ifill": 0}, "o:f3": {"exec": 100000, "ifill": 10}}
        promote, demote, rep = place_plan.plan(heat, self.FUNCS, "hw", 200)   # no spare room anywhere: only the 100 bytes f3 freed in lw, one byte of alignment each
        self.assertEqual(rep["bytes_without_room"], 200)                      # f3 freed 100 bytes in lw; a 100 byte function needs 101 with its alignment byte, so neither f1 nor f2 fits
        self.assertEqual(demote, {})

    def test_no_heat_no_promotion_and_ld_lines(self):
        promote, demote, rep = place_plan.plan({}, self.FUNCS, "hw", 1000)
        self.assertEqual(promote, {})
        self.assertEqual(rep["functions_promoted"], 0)
        self.assertEqual(place_plan.ld_lines([{"key": "c3:f_aa016", "size": 4}]), "    *c3.o(.text.f_aa016)\n")

    def test_cli_writes_include_files(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "heat.json").write_text(json.dumps({"o:f3": {"exec": 9999, "ifill": 1}, "o:f0": {"exec": 5, "ifill": 0}}))
            (d / "funcs.json").write_text(json.dumps(self.FUNCS))
            rc = place_plan.main(["--heat", str(d / "heat.json"), "--functions", str(d / "funcs.json"), "--fast", "hw", "--capacity", "200",
                                  "--spare", "lw=500", "--out", str(d / "plan.json"), "--ld-dir", str(d / "ld")])
            self.assertEqual(rc, 0)
            fast = (d / "ld" / "hw.ld.inc").read_text()
            self.assertIn("*o.o(.text.f3)", fast)
            self.assertEqual(place_plan.main(["--heat", str(d / "nope.json"), "--functions", str(d / "funcs.json"), "--fast", "hw", "--capacity", "1"]), 2)


class OpxStoreTest(unittest.TestCase):
    def test_build_lookup_roundtrip_and_merge(self):
        data = bytes(range(256)) * 4
        ops = bytearray(data)
        for i in (10, 11, 12, 40):
            ops[i] ^= 0xFF
        rs = opx_store.diff_ranges(data, bytes(ops), pad=8)
        self.assertEqual(rs, [(2, 19), (32, 17)])             # 10..12 and 40, each widened by 8, kept apart
        rs2 = opx_store.diff_ranges(data, bytes(ops), pad=16)
        self.assertEqual(len(rs2), 1)                         # close ranges merge
        store = opx_store.build(rs2, bytes(ops))
        for a in range(0, 100):
            expect = ops[a] if any(s <= a < s + n for s, n in rs2) else None
            self.assertEqual(opx_store.lookup(store, a), expect)

    def test_overlap_is_refused(self):
        with self.assertRaises(ValueError):
            opx_store.build([(0, 10), (5, 10)], bytes(32))

    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "data.bin").write_bytes(bytes(64))
            ops = bytearray(64)
            ops[20] = 7
            (d / "ops.bin").write_bytes(bytes(ops))
            self.assertEqual(opx_store.main(["build", str(d / "o.bin"), "--data", str(d / "data.bin"), "--ops", str(d / "ops.bin"), "--pad", "2"]), 0)
            self.assertEqual(opx_store.lookup((d / "o.bin").read_bytes(), 20), 7)
            self.assertEqual(opx_store.main(["show", str(d / "o.bin")]), 0)
            self.assertEqual(opx_store.main(["show", str(d / "missing.bin")]), 2)


class Vdp2PatternTest(unittest.TestCase):
    """The cycle words in sat_vdp2_cycles.h pass tools/vdp2_cycle_check.py for the layer set they serve, and a broken copy does not."""

    def words(self, name):
        text = (SATURN / "gfx/sat_vdp2_cycles.h").read_text()
        body = re.search(r"#define %s \{([^}]*)\}" % name, text).group(1)
        return [int(x.strip().rstrip("u"), 16) for x in body.split(",")]

    def spec(self):
        s = json.loads((SATURN / "gfx/vdp2_layout.example.json").read_text())
        text = (SATURN / "gfx/sat_vdp2_cycles.h").read_text()
        s["ramctl"] = int(re.search(r"SAT_V2_RAMCTL_SPLIT (0x[0-9a-f]+)", text).group(1), 16)
        return s

    def test_half_reduction_pattern_passes(self):
        words = self.words("SAT_V2_CYC_HALF")
        self.assertEqual(len(words), 8)
        errs, _, _ = chk.check_spec(self.spec(), words)
        self.assertEqual(errs, [])

    def test_flat_pattern_passes_without_reduction(self):
        spec = self.spec()
        for n in ("nbg0", "nbg1"):
            spec["layers"][n]["reduction"] = 1
        errs, _, _ = chk.check_spec(spec, self.words("SAT_V2_CYC_FLAT"))
        self.assertEqual(errs, [])

    def test_flat_pattern_is_too_few_reads_for_the_reduced_layers(self):
        errs, _, _ = chk.check_spec(self.spec(), self.words("SAT_V2_CYC_FLAT"))
        self.assertTrue(errs)

    def test_damaged_pattern_fails(self):
        words = self.words("SAT_V2_CYC_HALF")
        words[2] = 0xFFFF                                      # NBG0's reads gone
        errs, _, _ = chk.check_spec(self.spec(), words)
        self.assertTrue(errs)


class ReadmeTest(unittest.TestCase):
    def test_every_source_and_header_is_named_in_the_readme(self):
        text = (SATURN / "README.md").read_text()
        missing = [p.relative_to(SATURN).as_posix() for p in sorted(SATURN.rglob("*"))
                   if p.suffix in (".c", ".h", ".S", ".in", ".json") and p.relative_to(SATURN).as_posix() not in text and p.name not in text]
        self.assertEqual(missing, [], "files not named in saturn/README.md")

    def test_every_file_has_a_licence_line_and_an_origin(self):
        bad = []
        for p in sorted(SATURN.rglob("*")):
            if p.suffix in (".c", ".h", ".S", ".in"):
                head = p.read_text(encoding="utf-8")[:700]
                if "SPDX-License-Identifier: MIT" not in head or not re.search(r"avpsaturn (v0\.1\.0-beta|release/v0\.1\.2-beta)|[Ww]ritten for the kit", head):
                    bad.append(p.name)
        self.assertEqual(bad, [])

    def test_no_private_paths_or_game_names(self):
        bad = []
        for p in sorted(SATURN.rglob("*")) + sorted((ROOT / "tools").glob("fn_heat.py")) + [ROOT / "tools/place_plan.py", ROOT / "tools/opx_store.py"]:
            if p.is_file():
                t = p.read_text(encoding="utf-8")
                for pat in (r"[A-Za-z]:\\", r"/Users/", r"\bavsp_\w+", r"E:/", r"C:/"):
                    if re.search(pat, t):
                        bad.append((p.name, pat))
        self.assertEqual(bad, [])


class BuildCheckTest(unittest.TestCase):
    """Tier BUILD: every module compiles for the SH-2. Skipped when no cross compiler is found; a skip is not a pass."""

    def test_modules_compile_for_the_sh2(self):
        if not saturn_build_check.find_gcc():
            self.skipTest("no SH-2 cross compiler (set JO, SH_ELF_GCC or put sh-elf-gcc on PATH)")
        self.assertEqual(saturn_build_check.main(["--quiet"]), 0)

    def test_module_list_is_found(self):
        names = {p.name for p in saturn_build_check.modules()}
        self.assertTrue({"sat_boot.c", "sat_ctx.S", "sat_tilecache.c", "sat_vdp1.c"} <= names)


if __name__ == "__main__":
    unittest.main()
