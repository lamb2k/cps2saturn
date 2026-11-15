import pathlib
import struct
import tempfile
import unittest
import zlib

import _util  # noqa: F401
import lookdiff as ld

W, H = 40, 20


def image(fill=(10, 20, 30), patch=None):
    px = bytearray(bytes(fill) * (W * H))
    for (x0, y0, x1, y1), col in (patch or []):
        for y in range(y0, y1):
            for x in range(x0, x1):
                px[(y * W + x) * 3:(y * W + x) * 3 + 3] = bytes(col)
    return bytes(px)


def encode(w, h, ctype, chans, pixels, ftype, plte=None):
    """Tiny PNG encoder using one filter type for every row, to exercise the decoder's unfilter paths."""
    stride, rows, prev = w * chans, [], bytearray(w * chans)
    for y in range(h):
        row = bytearray(pixels[y * stride:(y + 1) * stride])
        out = bytearray()
        for i in range(stride):
            a = row[i - chans] if i >= chans else 0
            b = prev[i]
            c = prev[i - chans] if i >= chans else 0
            pred = {0: 0, 1: a, 2: b, 3: (a + b) >> 1, 4: ld._paeth(a, b, c)}[ftype]
            out.append((row[i] - pred) & 255)
        rows.append(bytes([ftype]) + bytes(out))
        prev = row
    def chunk(k, body):
        return struct.pack(">I", len(body)) + k + body + struct.pack(">I", zlib.crc32(k + body) & 0xFFFFFFFF)
    png = ld.PNG_SIG + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0))
    if plte:
        png += chunk(b"PLTE", plte)
    return png + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b"")


class DecoderTest(unittest.TestCase):
    def test_every_filter_and_colour_type(self):
        w, h = 7, 5
        rgb = bytes((x * 31 + y * 17 + c * 5) & 255 for y in range(h) for x in range(w) for c in range(3))
        rgba = bytes(v for i in range(w * h) for v in (*rgb[3 * i:3 * i + 3], 200))
        grey = bytes((i * 13) & 255 for i in range(w * h))
        idx = bytes(i % 3 for i in range(w * h))
        pal = bytes([10, 20, 30, 40, 50, 60, 70, 80, 90])
        want_pal = b"".join(pal[3 * v:3 * v + 3] for v in idx)
        d = pathlib.Path(tempfile.mkdtemp())
        for f in range(5):
            for name, ctype, chans, pix, plte, want in (("rgb", 2, 3, rgb, None, rgb), ("rgba", 6, 4, rgba, None, rgb),
                                                         ("grey", 0, 1, grey, None, b"".join(bytes((v,) * 3) for v in grey)),
                                                         ("pal", 3, 1, idx, pal, want_pal)):
                p = d / f"{name}{f}.png"
                p.write_bytes(encode(w, h, ctype, chans, pix, f, plte))
                self.assertEqual(ld.read_png(p), (w, h, want), f"{name} filter {f}")


class LookDiffTest(unittest.TestCase):
    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp())

    def png(self, name, px):
        p = self.d / name
        ld.write_png(p, W, H, px)
        return str(p)

    def test_png_round_trip(self):
        px = image(patch=[((3, 4, 9, 7), (200, 100, 50))])
        w, h, back = ld.read_png(self.png("a.png", px))
        self.assertEqual((w, h, back), (W, H, px))

    def test_changed_share_and_bbox(self):
        a = (W, H, image())
        b = (W, H, image(patch=[((10, 5, 20, 9), (255, 0, 0))]))   # 10 x 4 pixels
        r = ld.diff(a, b)
        self.assertEqual(r["changed"], 40)
        self.assertAlmostEqual(r["pct"], 100.0 * 40 / (W * H))
        self.assertEqual(r["bbox"], (10, 5, 20, 9))
        self.assertIsNone(ld.diff(a, a)["bbox"])

    def test_threshold_mask_and_crop(self):
        a = (W, H, image())
        b = (W, H, image(patch=[((0, 0, 40, 20), (12, 22, 32))]))   # +2 per channel everywhere
        self.assertEqual(ld.diff(a, b, threshold=24)["changed"], 0)
        self.assertEqual(ld.diff(a, b, threshold=1)["changed"], W * H)
        self.assertEqual(ld.diff(a, b, threshold=1, masks=[(0, 0, 40, 10)])["changed"], W * 10)
        self.assertEqual(ld.diff(a, b, threshold=1, crop=(0, 0, 10, 10))["total"], 100)

    def test_cli_pass_fail_and_diff_image(self):
        a = self.png("a.png", image())
        same = self.png("same.png", image())
        other = self.png("other.png", image(patch=[((0, 0, 4, 4), (255, 255, 255))]))
        out = self.d / "diff.png"
        self.assertEqual(ld.main([a, same]), 0)
        self.assertEqual(ld.main([a, other, "--out", str(out)]), 1)
        self.assertTrue(out.exists())
        w, h, _ = ld.read_png(out)
        self.assertEqual((w, h), (3 * W, H))
        self.assertEqual(ld.main([a, other, "--max-pct", "5"]), 0)       # 16 of 800 pixels = 2 %
        self.assertEqual(ld.main([a, other, "--mask", "0,0,4,4"]), 0)    # the changed box is masked off

    def test_folders_and_bad_input(self):
        for n in ("A", "B"):
            (self.d / n).mkdir()
            ld.write_png(self.d / n / "look_1.png", W, H, image())
        self.assertEqual(ld.main([str(self.d / "A"), str(self.d / "B")]), 0)
        (self.d / "junk.png").write_bytes(b"not a png")
        self.assertEqual(ld.main([str(self.d / "junk.png"), str(self.d / "A" / "look_1.png")]), 2)
        self.assertEqual(ld.main([str(self.d / "nothing.png"), str(self.d / "A" / "look_1.png")]), 2)

    def test_size_mismatch_fails(self):
        small = self.d / "small.png"
        ld.write_png(small, 4, 4, bytes(48))
        self.assertEqual(ld.main([self.png("a.png", image()), str(small)]), 1)


if __name__ == "__main__":
    unittest.main()
