"""The VDP2 state dump judge in tools/vdp2_cycle_check.py (--dump VRAM REGS): pattern names against the bank cell reads, built from synthetic VRAM and register files."""
import contextlib
import io
import pathlib
import struct
import tempfile
import unittest

import _util  # noqa: F401
import vdp2_cycle_check as chk

# Cycle words as in test_vdp2_cycle_check.GOOD: names of NBG0 to NBG2 in B1, cells in A0 (T4 T5 T6), CPU slots in A0/A1 and B0/B1.
GOOD = [0xFFFE, 0x456F, 0xFFFE, 0xFFFF, 0xFFFF, 0xFFFE, 0x012F, 0xFFFE]
BLANK = 0x40   # character number every name points at by default: byte 0x800, bank A0


def regs_file(pnc=0x8000, chctla=0x0000, chctlb=0x0000, maps=None, mpofn=0, plsz=0, bgon=0x0007, cycles=GOOD, ramctl=0x1300):
    """-> (bytes of a 0x120 byte register file, the dict). maps: per NBG (A, B, C, D) map register values; default one plane of 0x30 + n in all four."""
    r = {chk.TVMD: 0x8000, chk.RAMCTL: ramctl, chk.BGON: bgon, chk.CHCTLA: chctla, chk.CHCTLB: chctlb, chk.PLSZ: plsz, chk.MPOFN: mpofn}
    r.update(dict(zip(chk.CYC_OFFSETS, cycles)))
    r.update({0x78: 1, 0x7c: 1, 0x88: 1, 0x8c: 1})   # a register file holds every register: the increments are written 1.0 like the layout does
    for n in range(4):
        r[chk.PNC[n]] = pnc
        a, b, c, d = (maps or {}).get(n, (0x30 + n,) * 4)
        r[chk.MAPREGS[n][0]] = a | b << 8
        r[chk.MAPREGS[n][1]] = c | d << 8
    raw = bytearray(0x120)
    for o, v in r.items():
        struct.pack_into(">H", raw, o, v)
    return bytes(raw), r


def one_word_vram(name=BLANK, plane_bases=(0x60000, 0x62000, 0x64000), entries=0x1000):
    """512 KB VRAM with one word names `name` at the start of every listed plane (1x1 characters, one page of 64 x 64 names)."""
    v = bytearray(0x80000)
    for base in plane_bases:
        for i in range(entries):
            struct.pack_into(">H", v, base + 2 * i, name)
    return v


class DumpJudgeTest(unittest.TestCase):
    def judge(self, vram, regs, **kw):
        return chk.judge_dump(bytes(vram), regs, **kw)

    def test_good_dump_passes(self):
        _, regs = regs_file()
        self.assertEqual(self.judge(one_word_vram(), regs), [])

    def test_zero_names_are_an_error_even_in_a_bank_with_reads(self):
        _, regs = regs_file()
        v = one_word_vram()
        struct.pack_into(">H", v, 0x60000 + 2 * 7, 0)
        e = self.judge(v, regs)
        self.assertEqual(len(e), 1, e)
        self.assertIn("NBG0: 1 of 4096 names are 0", e[0])
        self.assertEqual(self.judge(v, regs, allow_zero_names=True), [])   # character 0 sits in A0, which has the cell reads

    def test_name_into_a_bank_without_cell_reads(self):
        v = one_word_vram()
        # supplement 0b01000 = character number bits 14..10 = 8: +0x2000 characters = +0x40000 bytes, B0 (no cell read)
        _, regs = regs_file(pnc=0x8000 | 0x08)
        e = self.judge(v, regs)
        self.assertEqual(len(e), 3, e)   # all three layers
        self.assertIn("no cell read for this layer", e[0])
        self.assertIn("B0", e[0])

    def test_supplement_bits_move_the_character_into_another_bank(self):
        _, regs = regs_file(pnc=0x8000 | 0x04)   # character bits 12 and up: +0x1000 chars = +0x20000 bytes: A1, which has no cell read here
        e = self.judge(one_word_vram(), regs)
        self.assertTrue(e and "A1" in e[0], e)
        _, regs = regs_file(pnc=0x8000 | 0x01)   # +0x400 chars = +0x8000 bytes: still A0
        self.assertEqual(self.judge(one_word_vram(), regs), [])

    def test_name_past_the_end_of_vram(self):
        _, regs = regs_file(pnc=0x8000 | 0x10)   # +0x4000 chars = 0x80000
        e = self.judge(one_word_vram(), regs)
        self.assertTrue(e and "outside the 512 KB" in e[0], e)

    def test_extended_character_numbers(self):
        _, regs = regs_file(pnc=0xC000)   # CNSM set: character number bits 11..0 from the name
        v = one_word_vram(name=0x0800)    # bit 11: +0x800 chars = 0x10000 bytes: still A0
        self.assertEqual(self.judge(v, regs), [])
        self.assertEqual(self.judge(one_word_vram(name=0x07FF), regs), [])

    def test_two_word_names(self):
        # two word names: pages of 0x4000 bytes, map value 0x18 = 0x60000; the character number is the low word, bits 14..0
        maps = {n: (0x18 + n,) * 4 for n in range(3)}
        _, regs = regs_file(pnc=0x0000, maps=maps)
        v = bytearray(0x80000)
        for n in range(3):
            for i in range(0x1000):
                struct.pack_into(">HH", v, 0x60000 + 0x4000 * n + 4 * i, 0x0000, BLANK)
        self.assertEqual(self.judge(v, regs), [])
        struct.pack_into(">HH", v, 0x60000, 0x0000, 0x2000)   # 0x2000 << 5 = 0x40000: B0
        e = self.judge(v, regs)
        self.assertEqual(len(e), 1, e)
        self.assertIn("NBG0: 1 of 4096 names", e[0])

    def test_two_by_two_characters_and_map_offset(self):
        # 2x2 characters: 32 x 32 names of 2 bytes a page (0x800 bytes); the page for B1 0x60000 is map value 0xC0 = MPOFN 3, register value 0
        maps = {n: (0,) * 4 for n in range(3)}
        _, regs = regs_file(chctla=0x0101, chctlb=0x0001, maps=maps, mpofn=0x0333)
        v = bytearray(0x80000)
        for n in range(3):
            for i in range(32 * 32):
                struct.pack_into(">H", v, 0x60000 + i * 2, BLANK)   # every plane is the same page: the four planes of a layer share it
        self.assertEqual(self.judge(v, regs), [])
        # a 2x2 character takes four cells: name 0x3FF is character 0xFFC, cells up to 0xFFF + ... = byte 0x1FFFF: the last byte of A0
        for i in range(32 * 32):
            struct.pack_into(">H", v, 0x60000 + i * 2, 0x03FF)
        self.assertEqual(self.judge(v, regs), [])
        # one more character number (supplement 0b00100 = bit 12) moves it into A1
        _, regs = regs_file(chctla=0x0101, chctlb=0x0001, maps=maps, mpofn=0x0333, pnc=0x8000 | 0x04)
        self.assertTrue(self.judge(v, regs))

    def test_a_layer_that_is_off_or_a_bitmap_is_not_read(self):
        _, regs = regs_file(bgon=0x0001)
        v = one_word_vram(plane_bases=(0x60000,))   # NBG1 and NBG2's planes are zero, but those layers are off
        self.assertEqual(self.judge(v, regs), [])
        _, regs = regs_file(chctla=0x0002, bgon=0x0001)   # NBG0 is a bitmap: no names
        self.assertEqual(self.judge(bytes(0x80000), regs), [])

    def test_short_vram_dump_is_bad_input(self):
        _, regs = regs_file()
        with self.assertRaises(chk.BadInput):
            chk.judge_dump(bytes(0x1000), regs)


class DumpCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def files(self, vram, raw):
        (self.d / "vram.bin").write_bytes(bytes(vram))
        (self.d / "regs.bin").write_bytes(raw)
        return [str(self.d / "vram.bin"), str(self.d / "regs.bin")]

    def run_main(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return chk.main(list(args))

    def test_exit_codes(self):
        raw, _ = regs_file()
        good = self.files(one_word_vram(), raw)
        self.assertEqual(self.run_main("--dump", *good), 0)
        bad = one_word_vram()
        struct.pack_into(">H", bad, 0x60000, 0)
        self.assertEqual(self.run_main("--dump", *self.files(bad, raw)), 1)
        self.assertEqual(self.run_main("--dump", *self.files(bad, raw), "--allow-zero-names"), 0)
        self.assertEqual(self.run_main("--dump", str(self.d / "missing.bin"), str(self.d / "regs.bin")), 2)
        (self.d / "short.bin").write_bytes(bytes(10))
        self.assertEqual(self.run_main("--dump", str(self.d / "vram.bin"), str(self.d / "short.bin")), 2)

    def test_a_zero_filled_register_file_fails_the_state_rules_too(self):
        _, regs = regs_file()
        regs.update({o: 0 for o in chk.ZOOM_REGS})
        raw = bytearray(0x120)
        for o, v in regs.items():
            struct.pack_into(">H", raw, o, v)
        self.assertEqual(self.run_main("--dump", *self.files(one_word_vram(), bytes(raw))), 1)


if __name__ == "__main__":
    unittest.main()
