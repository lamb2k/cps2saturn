import os
import pathlib
import tempfile
import unittest

import _util  # noqa: F401
import sector_store

SEC = sector_store.SEC


class SectorStoreTest(unittest.TestCase):
    def test_round_trip_and_dedupe(self):
        a, b, c = (bytes([i]) * SEC for i in (1, 2, 3))
        files = [a + b + c, b + c + a, os.urandom(SEC) + a]
        store, rounds = sector_store.build(files)
        for i, f in enumerate(files):
            self.assertEqual(sector_store.rebuild(store, i), f)
        self.assertEqual(len(store) // SEC, 1 + 1 + 4)   # header, run table, 4 unique sectors

    def test_cli_keep(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            for i in range(3):
                (root / f"R{i:03d}.BIN").write_bytes(bytes([i % 2]) * SEC * 2)
            rc = sector_store.main([str(root), "--keep", str(root / "kept")])
            self.assertEqual(rc, 0)
            self.assertTrue((root / "STORE.BIN").exists())
            self.assertEqual(len(list((root / "kept").glob("R*.BIN"))), 3)
            self.assertEqual(list(root.glob("R*.BIN")), [])


if __name__ == "__main__":
    unittest.main()
