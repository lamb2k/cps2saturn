import io
import pathlib
import unittest
from contextlib import redirect_stdout

import _util  # noqa: F401
import cfg
import mame_golden_run


class GoldenRunTest(unittest.TestCase):
    def test_env_from_config(self):
        c = cfg.load(_util.EXAMPLE)
        cmd, env, out = mame_golden_run.build(c, "g1", pathlib.Path("work"), "route.txt", "100", "50", True, 10)
        self.assertEqual(env["CPS2SAT_IRQ_TAP"], "0xe0e,0xe0f")
        self.assertEqual(env["CPS2SAT_WORK"], "0xff0000,0x10000")
        self.assertEqual(env["CPS2SAT_IO"], "0x800000-0x80ffff;0x618000-0x619fff")
        self.assertEqual(env["CPS2SAT_DELTA"], "1")
        self.assertTrue(env["CPS2SAT_ROUTE_BITS"].startswith(":IN2|Coin 1;"))
        self.assertIn("avspu", cmd)
        self.assertTrue(cmd[-1].endswith("golden.lua"))

    def test_dry_run(self):
        f = io.StringIO()
        with redirect_stdout(f):
            rc = mame_golden_run.main(["--config", str(_util.EXAMPLE), "--name", "x", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("CPS2SAT_OUT=", f.getvalue())

    def test_lua_scripts_read_the_same_names(self):
        lua = (_util.TOOLS / "mame" / "golden.lua").read_text()
        for name in ("CPS2SAT_OUT", "CPS2SAT_IRQ_TAP", "CPS2SAT_IRQ_VECTOR", "CPS2SAT_WORK", "CPS2SAT_OBJ",
                     "CPS2SAT_IO", "CPS2SAT_ROUTE", "CPS2SAT_ROUTE_BITS", "CPS2SAT_DELTA", "CPS2SAT_SAVE"):
            self.assertIn(f'"{name}"', lua)
        for f in ("dump_code_spaces.lua", "dump_rom_window.lua", "list_inputs.lua"):
            text = (_util.TOOLS / "mame" / f).read_text()
            self.assertNotIn("AVSP", text)
            self.assertIn("manager.machine", text)


if __name__ == "__main__":
    unittest.main()
