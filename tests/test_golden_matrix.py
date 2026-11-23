import io
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout

import _util  # noqa: F401
import golden_matrix
from golden_reader import compare
from test_golden_reader import delta, full, WS, OS


class GoldenMatrixTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name)
        self.ref = self.root / "ref"
        self.candidate = self.root / "candidate"
        self.config = self.root / "game.yaml"
        self.config.write_text(f"ram:\n  work_base: 0\n  work_size: {WS}\n  object_size: {OS}\n")
        self.ram = bytes(WS + OS)
        for side in (self.ref, self.candidate):
            for route in ("solo", "join"):
                (side / route).mkdir(parents=True)
                for delay in ("d0", "d1"):
                    (side / route / f"{delay}.bin").write_bytes(full(7, self.ram))

    def matrix(self, candidate):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = golden_matrix.main([str(self.ref), str(candidate), "--routes", "solo", "join",
                                     "--delays", "d0", "d1", "--config", str(self.config)])
        return rc, out.getvalue()

    def test_matrix(self):
        rc, out = self.matrix(self.candidate)
        self.assertEqual(rc, 0)
        self.assertIn("4/4 pairs matched", out)
        (self.candidate / "join/d1.bin").unlink()
        (self.ref / "join/d1.bin").unlink()
        rc, out = self.matrix(self.candidate)
        self.assertEqual(rc, 1)
        self.assertIn("join d1 FAIL", out)
        self.assertIn("3/4 pairs matched", out)

    def test_same_files_cannot_count(self):
        rc, out = self.matrix(self.ref)
        self.assertEqual(rc, 1)
        self.assertIn("0/4 pairs matched", out)

    def test_capture_length_irq_and_memory(self):
        ref, cand = self.ref / "solo/d0.bin", self.candidate / "solo/d0.bin"
        for right, message in [(b"", "lengths differ"), (full(9, self.ram), "IRQ mismatch"),
                               (full(7, self.ram[:-1] + b"x"), "object +")]:
            with self.subTest(message=message):
                cand.write_bytes(right)
                ok, report = compare(ref, cand, 0, WS, OS, False)
                self.assertFalse(ok)
                self.assertIn(message, report)
        ref.write_bytes(b"")
        cand.write_bytes(b"")
        self.assertFalse(compare(ref, cand, 0, WS, OS, False)[0])

    def test_malformed_captures(self):
        ref = self.ref / "solo/d0.bin"
        for data, is_delta in [(b"VBL", False), (full(7, self.ram)[:-1], False),
                               (delta(7, [(0, self.ram)])[:-1], True),
                               (delta(7, [(WS + OS, b"abcd")]), True)]:
            with self.subTest(data=data):
                ref.write_bytes(data)
                with self.assertRaises(ValueError):
                    compare(ref, ref, 0, WS, OS, is_delta)


if __name__ == "__main__":
    unittest.main()
