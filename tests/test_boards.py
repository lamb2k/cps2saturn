import copy
import pathlib
import tempfile
import unittest

import _util  # noqa: F401
import boards
import cfg
import golden_reader
import mame_golden_run


def example(board=None, drop_objects=False, **video):
    c = copy.deepcopy(cfg.load(_util.EXAMPLE))
    if board:
        c["game"]["board"] = board
    if drop_objects:
        del c["ram"]["object_base"], c["ram"]["object_size"]
    if video:
        c["video"] = video
    return c


def run_args(c):
    return mame_golden_run.build(c, "g1", pathlib.Path("work"), "route.txt", "100", "50", True, 10)


class BoardKeyTest(unittest.TestCase):
    def test_missing_board_means_cps2(self):
        self.assertEqual(boards.name(example()), "cps2")

    def test_unknown_board_is_refused(self):
        with self.assertRaises(SystemExit):
            boards.name(example("cps3"))

    def test_cps2_by_name_changes_nothing(self):
        self.assertEqual(run_args(example()), run_args(example("cps2")))

    def test_cps2_keeps_its_fixed_object_ram(self):
        _, env, _ = run_args(example("cps2"))
        self.assertEqual(env["CPS2SAT_OBJ"], "0x708000,0x2000")
        self.assertNotIn("CPS2SAT_OBJ_REG", env)


class Cps1CaptureTest(unittest.TestCase):
    def test_object_table_follows_the_cps_a_register(self):
        for board in ("cps1", "cpsdash"):
            _, env, _ = run_args(example(board, drop_objects=True))
            self.assertEqual(env["CPS2SAT_OBJ"], "0x900000,0x800", board)
            self.assertEqual(env["CPS2SAT_OBJ_REG"], "0x800100,0x800", board)

    def test_config_overrides_the_board_defaults(self):
        c = example("cps1", drop_objects=True, cps_a=0x800200)
        c["ram"]["object_size"] = 0x1000
        _, env, _ = run_args(c)
        self.assertEqual(env["CPS2SAT_OBJ"], "0x900000,0x1000")
        self.assertEqual(env["CPS2SAT_OBJ_REG"], "0x800200,0x800")

    def test_fixed_object_table_can_be_forced(self):
        c = example("cps1")
        c["ram"]["object_table"] = "fixed"
        _, env, _ = run_args(c)
        self.assertEqual(env["CPS2SAT_OBJ"], "0x708000,0x2000")
        self.assertNotIn("CPS2SAT_OBJ_REG", env)

    def test_golden_reader_uses_the_board_object_size(self):
        self.assertEqual(golden_reader.sizes(example("cps1", drop_objects=True)), (0xFF0000, 0x10000, 0x800))
        self.assertEqual(golden_reader.sizes(example()), (0xFF0000, 0x10000, 0x2000))


class Cps1ExampleTest(unittest.TestCase):
    PATH = _util.ROOT / "configs" / "cps1.example.yaml"

    def test_loads_with_and_without_pyyaml(self):
        text = self.PATH.read_text()
        for c in (cfg.load(self.PATH), cfg._expand(cfg.parse_mini_yaml(text))):
            self.assertEqual(boards.name(c), "cpsdash")
            self.assertEqual(boards.object_table(c), "register")
            self.assertEqual(len(cfg.get(c, "video.priority")), 4)
            self.assertEqual(len(cfg.get(c, "video.layer_enable_masks")), 3)
            self.assertEqual(cfg.get(c, "graphics.mapper.ranges")[0][0], "sprites scroll1 scroll2 scroll3")

    def test_runner_dry_run(self):
        _, env, _ = run_args(cfg.load(self.PATH))
        self.assertEqual(env["CPS2SAT_OBJ"], "0x900000,0x800")
        self.assertEqual(env["CPS2SAT_OBJ_REG"], "0x800100,0x800")


class BaselineTest(unittest.TestCase):
    def test_nvram_and_cfg_baselines_are_copied(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "nv").mkdir()
            (d / "nv" / "eeprom").write_bytes(b"\0" * 4)
            (d / "dips").mkdir()
            (d / "dips" / "avspu.cfg").write_text("<mameconfig/>")
            c = example()
            c["paths"]["nvram_baseline"] = str(d / "nv")
            c["paths"]["cfg_baseline"] = str(d / "dips")
            out = d / "run"
            out.mkdir()
            mame_golden_run.seed(c, out)
            self.assertTrue((out / "nvram" / "avspu" / "eeprom").exists())
            self.assertEqual((out / "cfg" / "avspu.cfg").read_text(), "<mameconfig/>")

    def test_no_baselines_still_makes_the_cfg_folder(self):
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d)
            c = example()
            c["paths"]["nvram_baseline"] = ""
            mame_golden_run.seed(c, out)
            self.assertTrue((out / "cfg").is_dir())
            self.assertFalse((out / "nvram").exists())


class LuaTest(unittest.TestCase):
    def test_scripts_cope_without_an_opcode_space(self):
        golden = (_util.TOOLS / "mame" / "golden.lua").read_text()
        self.assertIn('"CPS2SAT_OBJ_REG"', golden)
        self.assertIn('spaces["opcodes"] or prog', golden)
        self.assertIn("install_write_tap", golden)
        dump = (_util.TOOLS / "mame" / "dump_code_spaces.lua").read_text()
        self.assertIn("NO_OPCODE_SPACE", dump)


if __name__ == "__main__":
    unittest.main()
