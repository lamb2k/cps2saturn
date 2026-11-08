import pathlib
import tempfile
import unittest

import _util  # noqa: F401
import make_cue


class MakeCueTest(unittest.TestCase):
    def test_package(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            src = root / "src"
            src.mkdir()
            (src / "game.iso").write_bytes(bytes(2048))
            for n in (2, 3):
                (src / f"t{n:02d}.raw").write_bytes(bytes(2352))
            out = root / "out"
            make_cue.main([str(out), str(src / "game.iso"), "--tracks", str(src), "--commit", "abc", "--copy"])
            cue = (out / "game.cue").read_text()
            self.assertIn('TRACK 01 MODE1/2048', cue)
            self.assertIn('TRACK 03 AUDIO', cue)
            sums = (out / "SHA256SUMS.txt").read_text().splitlines()
            self.assertEqual(sums[0], "# commit abc")
            self.assertEqual(len(sums), 1 + 4)       # iso, cue, two tracks


if __name__ == "__main__":
    unittest.main()
