import pathlib
import subprocess
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


def git(root, *args):
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                    "-c", "commit.gpgsign=false", *args], check=True, capture_output=True)


def have_git():
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


PNG_LIKE = b"\x89PNG\x00\x00"


@unittest.skipUnless(have_git(), "git not installed")
class HistoryTest(unittest.TestCase):
    def make_repo(self):
        d = pathlib.Path(tempfile.mkdtemp())
        git(d, "init", "-q")
        (d / "ok.md").write_text("plain words\n")
        git(d, "add", "-A")
        git(d, "commit", "-q", "-m", "clean")
        return d

    def test_deleted_file_is_still_found_in_history(self):
        d = self.make_repo()
        (d / "secret.iso").write_bytes(b"x")
        (d / "notes.txt").write_text("see " + "C" + ":" + "\\" + "Users" + "\\" + "me\n")
        git(d, "add", "-A")
        git(d, "commit", "-q", "-m", "oops")
        git(d, "rm", "-q", "secret.iso", "notes.txt")
        git(d, "commit", "-q", "-m", "remove")
        self.assertEqual(hygiene_scan.scan(d), [])   # the working tree is clean
        n, found = hygiene_scan.scan_history(d)
        text = "\n".join(found)
        self.assertGreaterEqual(n, 3)
        self.assertIn("secret.iso@", text)
        self.assertIn("blocked type .iso", text)
        self.assertIn("drive-letter path", text)
        self.assertEqual(hygiene_scan.main([str(d), "--history"]), 1)

    def test_oversize_blob_in_history(self):
        d = self.make_repo()
        (d / "big.txt").write_text("a" * (hygiene_scan.MAX_BYTES + 1))
        git(d, "add", "-A")
        git(d, "commit", "-q", "-m", "big")
        _, found = hygiene_scan.scan_history(d)
        self.assertTrue(any("big.txt@" in f and "over" in f for f in found), found)

    def test_clean_history_passes(self):
        d = self.make_repo()
        self.assertEqual(hygiene_scan.main([str(d), "--history"]), 0)

    def test_release_media_allowlist(self):
        d = self.make_repo()
        (d / "docs" / "media").mkdir(parents=True)
        (d / "docs" / "other").mkdir()
        (d / "docs" / "media" / "shot.png").write_bytes(PNG_LIKE)
        (d / "docs" / "media" / "game.iso").write_bytes(b"x")
        (d / "docs" / "other" / "shot.png").write_bytes(PNG_LIKE + b"1")
        git(d, "add", "-A")
        git(d, "commit", "-q", "-m", "media")
        _, found = hygiene_scan.scan_history(d, ["docs/media"])
        text = "\n".join(found)
        self.assertNotIn("docs/media/shot.png", text)     # approved folder, media type
        self.assertIn("docs/media/game.iso", text)        # approved folder, but not a media type
        self.assertIn("docs/other/shot.png", text)        # media outside the approved folder
        # the same allowlist from a file, in the working-tree scan
        (d / ".hygiene-media").write_text("# approved\ndocs/media/\n")
        wt = "\n".join(hygiene_scan.scan(d, every=True, allow=hygiene_scan.load_allow(d)))
        self.assertNotIn("docs/media/shot.png", wt)
        self.assertIn("docs/other/shot.png", wt)
        # CLI: allow both folders; only the iso is left, and it stays in history after it is deleted
        args = [str(d), "--history", "--allow-media", "docs/media/", "--allow-media", "docs/other/"]
        self.assertEqual(hygiene_scan.main(args), 1)
        (d / "docs" / "media" / "game.iso").unlink()
        git(d, "add", "-A")
        git(d, "commit", "-q", "-m", "drop iso")
        self.assertEqual(hygiene_scan.main(args), 1)

    def test_not_a_repo_is_bad_input(self):
        d = pathlib.Path(tempfile.mkdtemp())
        self.assertEqual(hygiene_scan.main([str(d), "--history"]), 2)


if __name__ == "__main__":
    unittest.main()
