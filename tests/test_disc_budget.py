import pathlib
import tempfile
import unittest

import _util  # noqa: F401
import disc_budget
import make_cue


class DiscBudgetTest(unittest.TestCase):
    def test_cue_count(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root / "g.iso").write_bytes(bytes(2048 * 10))
            (root / "t02.raw").write_bytes(bytes(2352 * 75))
            (root / "g.cue").write_text(make_cue.cue_text("g.iso", ["t02.raw"]))
            data, audio, gaps, tracks = disc_budget.from_cue(root / "g.cue", 150)
            self.assertEqual((data, audio, gaps, tracks), (10, 75, 150, 1))
            self.assertEqual(disc_budget.report(data, audio, gaps, tracks, 360000), 0)
            self.assertEqual(disc_budget.report(data, audio, gaps, tracks, 100), 1)


if __name__ == "__main__":
    unittest.main()
