import struct
import unittest

import _util  # noqa: F401
import dis68k

try:
    import capstone  # noqa: F401
    HAVE = True
except ImportError:
    HAVE = False


class Dis68kTest(unittest.TestCase):
    def test_vectors(self):
        img = struct.pack(">II", 0x00FF8000, 0x00000400) + bytes(0x100)
        v = dis68k.vectors(img)
        self.assertIn("00ff8000", v[0])
        self.assertIn("00000400", v[1])

    @unittest.skipUnless(HAVE, "capstone not installed")
    def test_nop_and_xref(self):
        # nop; move.w $00ff1234.l,d0; rts
        op = bytes.fromhex("4e71" "3039 00ff1234" "4e75")
        lines = dis68k.dis(op, 0, len(op))
        self.assertTrue(lines[0].endswith("nop"))
        self.assertTrue(any("rts" in l for l in lines))
        self.assertTrue(dis68k.xref(op, 0xFF1234))


if __name__ == "__main__":
    unittest.main()
