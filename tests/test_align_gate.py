import pathlib
import tempfile
import unittest

import _util  # noqa: F401
import align_gate as g

# `nm -S -n` style, synthetic. Example addresses only.
NM_GOOD = """\
06004000 00000040 D table_a
06004040 00000006 r words_b
06004046 00000003 r bytes_c
06004049 00000001 b flag
06004050 00000008 B buf_d
06004100 00000020 T some_function
"""
NM_BAD = NM_GOOD + """\
06004202 00000008 r misplaced_longs
06004303 00000004 d odd_table
06004402 00000004 d bytes_only_ok
06004502 00000010 D base_table
"""


class SymbolTest(unittest.TestCase):
    def check(self, text, allow=None, must=None):
        hits = []
        n = g.check_symbols(g.parse_nm(text), allow or {}, must or {}, hits)
        return n, hits

    def test_good_nm_is_clean(self):
        n, hits = self.check(NM_GOOD)
        self.assertEqual(hits, [])
        self.assertEqual(n, 5)   # text symbols and odd-sized byte data need nothing more

    def test_misaligned_symbols_are_caught(self):
        _, hits = self.check(NM_BAD)
        text = "\n".join(hits)
        self.assertIn("misplaced_longs", text)    # 8 bytes at 2 mod 4: needs 4
        self.assertIn("odd_table", text)          # 4 bytes at an odd address
        self.assertNotIn("words_b", text)
        self.assertNotIn("some_function", text)   # code is not data

    def test_allowlist_and_must_align(self):
        _, hits = self.check(NM_BAD, allow={"misplaced_longs": "bytes only", "odd_table": "bytes only",
                                            "bytes_only_ok": "bytes only", "base_table": "r"})
        self.assertEqual(hits, [])
        _, hits = self.check(NM_GOOD, must={"words_b": 4})   # 06004040 + 0 is fine, 6 bytes: forced to 4 and it is
        self.assertEqual(hits, [])
        _, hits = self.check(NM_GOOD, must={"bytes_c": 4})
        self.assertEqual(len(hits), 1)


class SourceTest(unittest.TestCase):
    def tree(self, files):
        d = pathlib.Path(tempfile.mkdtemp())
        for name, text in files.items():
            (d / name).write_text(text)
        return d

    def test_accessor_offsets(self):
        src = self.tree({"x.c": "u32 a(u8*p){return get32(p + 6);}\n"
                                "void b(u8*p){put16(p + 3, 1);}\n"
                                "u32 c(u8*p){return get32(p + 8);}\n"
                                "u16 d(u8*p){return get16(p + 2);}\n"
                                "u32 e(u8*p){return get32(p + (n + 58) * 32 + k);}\n"})
        hits = []
        n = g.check_offsets(src, {"get32": 4, "put16": 2, "get16": 2}, hits)
        self.assertEqual(n, 5)
        self.assertEqual(len(hits), 2, hits)
        self.assertIn("x.c:1", hits[0])
        self.assertIn("x.c:2", hits[1])

    def test_sites_need_review(self):
        text = ("void f(u8*p){ u32 *q = (u32 *)p; }\n"
                "void h(void){ *(volatile u32 *)0x25fe0000 = 1; }\n"
                "void k(u32 v){ *(volatile u32 *)&v = 1; }\n")
        src = self.tree({"x.c": text})
        found = g.site_lines(src)
        self.assertEqual(len(found), 1)   # the byte pointer cast only
        hits = []
        g.check_sites(src, {}, hits)
        self.assertEqual(len(hits), 1)
        key = found[0][3]
        hits = []
        g.check_sites(src, {key: "p is 4 aligned by the caller"}, hits)
        self.assertEqual(hits, [])
        (src / "x.c").write_text(text.replace("(u32 *)p", "(u32 *)(p + 2)"))   # an edited line needs a new review
        hits = []
        g.check_sites(src, {key: "p is 4 aligned by the caller"}, hits)
        self.assertEqual(len(hits), 1)

    def test_sites_file_round_trip(self):
        # A sites file written from --list-sites keys (which hold one space) must be read back as reviewed.
        src = self.tree({"x.c": "void f(u8*p){ u32 *q = (u32 *)p; }\n"})
        key = g.site_lines(src)[0][3]
        self.assertIn(" ", key)
        sites = src / "sites.txt"
        sites.write_text(f"# reviewed\n{key} p is 4 aligned by the caller\n", encoding="utf-8")
        reviewed = g.load_list(str(sites))
        self.assertEqual(reviewed.get(key), "p is 4 aligned by the caller")
        hits = []
        g.check_sites(src, reviewed, hits)
        self.assertEqual(hits, [])


class CliTest(unittest.TestCase):
    def test_exit_codes(self):
        d = pathlib.Path(tempfile.mkdtemp())
        (d / "good.nm").write_text(NM_GOOD)
        (d / "bad.nm").write_text(NM_BAD)
        (d / "empty.nm").write_text("nothing useful here\n")
        (d / "allow.txt").write_text("# reviewed\nmisplaced_longs byte data\nodd_table byte data\nbytes_only_ok byte data\n"
                                     "base_table byte data\n")
        self.assertEqual(g.main(["--nm-file", str(d / "good.nm")]), 0)
        self.assertEqual(g.main(["--nm-file", str(d / "bad.nm")]), 1)
        self.assertEqual(g.main(["--nm-file", str(d / "bad.nm"), "--allow", str(d / "allow.txt")]), 0)
        self.assertEqual(g.main(["--nm-file", str(d / "empty.nm")]), 2)
        self.assertEqual(g.main(["--nm-file", str(d / "missing.nm")]), 2)
        self.assertEqual(g.main([]), 2)


if __name__ == "__main__":
    unittest.main()
