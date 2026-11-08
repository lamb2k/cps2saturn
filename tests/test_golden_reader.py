import pathlib
import struct
import tempfile
import unittest

import _util  # noqa: F401
import golden_reader

WS, OS = 0x20, 0x10


def full(irq, ram):
    return b"VBLK" + struct.pack(">I", irq) + bytes(64) + ram


def delta(irq, runs):
    out = b"VBLK" + struct.pack(">I", irq) + bytes(64) + struct.pack(">I", len(runs))
    for first, words in runs:
        out += struct.pack(">HH", first, len(words) // 4) + words
    return out


class GoldenReaderTest(unittest.TestCase):
    def test_full_and_delta_agree(self):
        a = bytes(range(WS + OS))
        b = bytearray(a)
        b[4:8] = b"\xde\xad\xbe\xef"
        with tempfile.TemporaryDirectory() as d:
            pf, pd = pathlib.Path(d) / "f.bin", pathlib.Path(d) / "d.bin"
            pf.write_bytes(full(0, a) + full(1, bytes(b)))
            pd.write_bytes(delta(0, [(0, a)]) + delta(1, [(1, b"\xde\xad\xbe\xef")]))
            rf = [m for _, _, m in golden_reader.records(pf, WS, OS, False)]
            rd = [m for _, _, m in golden_reader.records(pd, WS, OS, True)]
            self.assertEqual(rf, rd)
            self.assertEqual(rf[1], bytes(b))


if __name__ == "__main__":
    unittest.main()
