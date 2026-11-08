import os
import unittest

import _util  # noqa: F401
import cfg


class CfgTest(unittest.TestCase):
    def test_example_loads(self):
        c = cfg.load(_util.EXAMPLE)
        self.assertEqual(cfg.get(c, "game.set"), "avspu")
        self.assertEqual(cfg.get(c, "cpu.irq_tap"), [0xE0E, 0xE0F])
        self.assertEqual(cfg.get(c, "ram.io_ranges")[0], [0x800000, 0x80FFFF])
        self.assertEqual(len(cfg.get(c, "inputs.route_bits")), 18)
        self.assertEqual(cfg.get(c, "rounds.page_size"), 0x400)

    def test_mini_parser(self):
        y = "\n".join(["top:", "  b: 0x10  # c", '  s: "x # y"', "  ls:", "    - 1", "    - two",
                       "  i: [1, [2, 3]]", "t: true", ""])
        d = cfg.parse_mini_yaml(y)
        self.assertEqual(d, {"top": {"b": 16, "s": "x # y", "ls": [1, "two"], "i": [1, [2, 3]]}, "t": True})

    def test_env_expand(self):
        os.environ["CPS2SAT_TEST_X"] = "abc"
        self.assertEqual(cfg._expand({"p": "${CPS2SAT_TEST_X}/d"}), {"p": "abc/d"})


if __name__ == "__main__":
    unittest.main()
