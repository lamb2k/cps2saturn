import unittest

import _util  # noqa: F401
import ip_bin


def header(load=0x06004000, embedded=0x1014):
    b = bytearray(0x1800)
    b[:16] = ip_bin.HWID
    b[0xE0:0xE4] = (0x1800).to_bytes(4, "big")
    b[0xF0:0xF4] = load.to_bytes(4, "big")
    b[0xF4:0xF8] = (0x100).to_bytes(4, "big")
    b[embedded:embedded + 4] = load.to_bytes(4, "big")
    return bytes(b)


class IpBinTest(unittest.TestCase):
    def test_fields_and_patch(self):
        src = header()
        self.assertTrue(ip_bin.fields(src)["hwid_ok"])
        out = ip_bin.patch(src, 0x06010000, 0, 0x1014, 0x1800)
        f = ip_bin.fields(out)
        self.assertEqual((f["load"], f["read"]), (0x06010000, 0))
        self.assertEqual(ip_bin.be32(out, 0x1014), 0x06010000)

    def test_refuses_unexpected_shape(self):
        src = bytearray(header())
        src[0x400:0x404] = (0x06004000).to_bytes(4, "big")   # a stray copy
        with self.assertRaises(ValueError):
            ip_bin.patch(bytes(src), 0x06010000, 0, 0x1014, 0x1800)
        with self.assertRaises(ValueError):
            ip_bin.patch(header(), 0x06010000, 0, 0x1014, 0x2000)


if __name__ == "__main__":
    unittest.main()
