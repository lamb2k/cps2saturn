import pathlib
import tempfile
import unittest

import _util  # noqa: F401
import hygiene_scan


class HygieneTest(unittest.TestCase):
    def test_clean_and_dirty(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root / "ok.md").write_text("plain words\n")
            self.assertEqual(hygiene_scan.scan(root, every=True), [])
            (root / "game.iso").write_bytes(b"x")
            (root / "blob.dat").write_bytes(b"a\0b")
            (root / "leak.txt").write_text("see " + "C" + ":" + "\\" + "Users" + "\\" + "me\n")
            (root / "key.txt").write_text("gh" + "p_" + "A" * 30 + "\n")
            found = "\n".join(hygiene_scan.scan(root, every=True))
            self.assertIn("blocked type .iso", found)
            self.assertIn("binary content", found)
            self.assertIn("drive-letter path", found)
            self.assertIn("GitHub token", found)

    def test_repo_is_clean(self):
        self.assertEqual(hygiene_scan.scan(_util.ROOT), [])


if __name__ == "__main__":
    unittest.main()
