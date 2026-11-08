import pathlib
import tempfile
import unittest

import _util  # noqa: F401
import iso_verify

SEC = 2048


def rec(extent, size, flags, name: bytes) -> bytes:
    n = 33 + len(name)
    n += n % 2
    r = bytearray(n)
    r[0] = n
    r[2:6] = extent.to_bytes(4, "little")
    r[10:14] = size.to_bytes(4, "little")
    r[25] = flags
    r[32] = len(name)
    r[33:33 + len(name)] = name
    return bytes(r)


def tiny_iso(payload: bytes) -> bytes:
    img = bytearray(SEC * 20)
    pvd = bytearray(SEC)
    pvd[0], pvd[1:6] = 1, b"CD001"
    root = rec(18, SEC, 2, b"\x00")
    pvd[156:156 + len(root)] = root
    img[16 * SEC:17 * SEC] = pvd
    d = rec(18, SEC, 2, b"\x00") + rec(18, SEC, 2, b"\x01") + rec(19, len(payload), 0, b"A.TXT;1")
    img[18 * SEC:18 * SEC + len(d)] = d
    img[19 * SEC:19 * SEC + len(payload)] = payload
    return bytes(img)


class IsoVerifyTest(unittest.TestCase):
    def test_read_and_verify(self):
        img = tiny_iso(b"hello")
        self.assertEqual(iso_verify.read_path(img, "a.txt"), b"hello")
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d)
            (p / "t.iso").write_bytes(img)
            (p / "good").write_bytes(b"hello")
            (p / "bad").write_bytes(b"world")
            self.assertEqual(iso_verify.main([str(p / "t.iso"), "A.TXT", "--equals", str(p / "good")]), 0)
            self.assertEqual(iso_verify.main([str(p / "t.iso"), "A.TXT", "--equals", str(p / "bad")]), 1)
        e, s, _ = iso_verify.root(img)
        self.assertEqual(iso_verify.walk(img, e, s), [("A.TXT", 19, 5)])


if __name__ == "__main__":
    unittest.main()
