"""Host tests of the saturn/ modules (tier HOST): the pure C compiled for a PC and driven from here.

The C sources under test are the same files a console build compiles (with -DSAT_HOST where they touch memory-mapped chips, so the chips become arrays or
logging callbacks). A host C compiler is needed (cc, gcc or clang on PATH); without one every test here is skipped, not passed.
Passing these is not a console result: nothing here runs on an SH-2.
"""
import os
import pathlib
import random
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib

import _util  # noqa: F401
import opx_store
import sector_store

ROOT = pathlib.Path(__file__).resolve().parents[1]
CDIR = ROOT / "tests" / "c"
CC = os.environ.get("CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
TMP = tempfile.TemporaryDirectory()
BUILT = {}


def build(name, extra_sources=()):
    """Compile tests/c/NAME.c with the listed saturn/ sources; cached per run. Returns the executable path."""
    if name in BUILT:
        return BUILT[name]
    exe = pathlib.Path(TMP.name) / name
    cmd = [CC, "-std=gnu99", "-O1", "-Wall", "-Wextra", "-Werror", "-DSAT_HOST=1", str(CDIR / f"{name}.c"),
           *[str(ROOT / s) for s in extra_sources], "-o", str(exe)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise AssertionError("compile failed:\n" + r.stdout + r.stderr)
    BUILT[name] = str(exe)
    return BUILT[name]


def run(exe, *args):
    return subprocess.run([exe, *[str(a) for a in args]], capture_output=True, text=True)


@unittest.skipUnless(CC, "no host C compiler")
class ModuleScenarioTests(unittest.TestCase):
    """Scenario tests written in C (tests/c/t_*.c); each prints PASS."""

    def scenario(self, name, *sources):
        r = run(build(name, sources))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PASS", r.stdout)

    def test_tilecache(self):
        self.scenario("t_tilecache", "saturn/gfx/sat_tilecache.c")

    def test_cart_soak(self):
        self.scenario("t_soak", "saturn/boot/sat_cart_soak.c")

    def test_vdp1_plot_protocol(self):
        self.scenario("t_vdp1", "saturn/gfx/sat_vdp1.c")

    def test_vdp2_latch_and_layout(self):
        self.scenario("t_vdp2", "saturn/gfx/sat_vdp2.c")

    def test_vdp2_writer_wait(self):
        self.scenario("t_vdp2wait", "saturn/gfx/sat_vdp2.c")

    def test_pad_sequence(self):
        self.scenario("t_pad", "saturn/rt/sat_pad.c")

    def test_scsp_and_cdda(self):
        self.scenario("t_audio", "saturn/audio/sat_scsp.c", "saturn/audio/sat_cdda.c")

    def test_layer_memo(self):
        self.scenario("t_layer", "saturn/gfx/sat_layer.c")

    def test_handoff(self):
        self.scenario("t_sync", "saturn/rt/sat_sync.c")

    def test_readout(self):
        self.scenario("t_readout", "saturn/rt/sat_readout.c")


@unittest.skipUnless(CC, "no host C compiler")
class StoreTests(unittest.TestCase):
    """sat_store.c reads what tools/sector_store.py wrote."""

    def make_rounds(self):
        rnd = random.Random(7)
        shared = bytes(rnd.randrange(256) for _ in range(2048 * 3))   # three sectors every round shares, so the store has runs shorter than a round
        rounds, expect = [], []
        for r in range(4):
            own = bytes([r + 1]) * 2048 * (r + 1)
            regions = [(0x1000, shared), (1, b""), (0x20000, own), (0x40000, shared[:2048] + bytes(rnd.randrange(256) for _ in range(2048)))]
            head = struct.pack(">I", len(regions)) + b"".join(struct.pack(">II", d, len(b)) for d, b in regions)
            rounds.append(head + bytes(2048 - len(head)) + b"".join(b for _, b in regions))
            expect.append(regions)
        return rounds, expect

    def test_every_round_loads_to_its_addresses(self):
        rounds, expect = self.make_rounds()
        store, _ = sector_store.build(rounds)
        exe = build("t_store", ["saturn/cd/sat_store.c"])
        d = pathlib.Path(TMP.name)
        (d / "STORE.BIN").write_bytes(store)
        for i, regions in enumerate(expect):
            r = run(exe, d / "STORE.BIN", i, d / f"out{i}.bin")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("marks 1", r.stdout)
            self.assertIn(f"sectors {len(rounds[i]) // 2048}", r.stdout)
            mem = (d / f"out{i}.bin").read_bytes()
            for dest, b in regions:
                if dest != 1:
                    self.assertEqual(mem[dest:dest + len(b)], b, f"round {i} region at {dest:#x}")

    def test_bad_store_and_round(self):
        rounds, _ = self.make_rounds()
        store, _ = sector_store.build(rounds)
        d = pathlib.Path(TMP.name)
        (d / "S2.BIN").write_bytes(store)
        r = run(build("t_store", ["saturn/cd/sat_store.c"]), d / "S2.BIN", "bad", d / "unused.bin")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


def raw_deflate(b):
    co = zlib.compressobj(9, zlib.DEFLATED, -15, 9)
    return co.compress(b) + co.flush()


@unittest.skipUnless(CC, "no host C compiler")
class LzTests(unittest.TestCase):
    """sat_lzdec.h decodes streams zlib wrote, in place, the way a loader lays them out."""

    def layout(self, raw, blocks, tail):
        streams = [raw_deflate(raw[o:o + n]) for o, n in blocks]
        pad = lambda n: (n + 2047) // 2048 * 2048
        padded = sum(pad(len(s)) for s in streams)
        buf = bytearray(len(raw))
        base = len(raw) - padded
        off = 0
        for s in streams:
            buf[base + off:base + off + len(s)] = s
            off += pad(len(s))
        head = struct.pack("<III", len(raw), len(blocks), tail) + b"".join(struct.pack("<II", n, len(s)) for (_, n), s in zip(blocks, streams))
        return head + bytes(buf), padded

    def decode(self, raw, blocks, tail):
        d = pathlib.Path(TMP.name)
        data, padded = self.layout(raw, blocks, tail)
        if padded > len(raw):
            return None
        (d / "lz.in").write_bytes(data)
        r = run(build("t_lz"), d / "lz.in", d / "lz.out")
        return r.returncode, (d / "lz.out").read_bytes()

    def test_in_place_blocks(self):
        rnd = random.Random(3)
        words = [bytes(rnd.randrange(256) for _ in range(rnd.randrange(3, 9))) for _ in range(40)]
        raw = b"".join(rnd.choice(words) for _ in range(40000))[:131072]
        blocks = [(0, 32768), (32768, 32768), (65536, 32768), (98304, 32768)]
        ok = []
        for tail in (0, 512, 1024, 2048, 4096, 7168):
            rc, out = self.decode(raw, blocks, tail) or (None, None)
            if rc == 0:
                self.assertEqual(out, raw)
                ok.append(tail)
        self.assertTrue(ok, "no tail size decoded in place")

    def test_stored_and_fixed_blocks(self):
        # a short stream is a fixed-Huffman block, incompressible data is stored: both block types
        raw = bytes(random.Random(1).randrange(256) for _ in range(6000)) + b"abc" * 400
        self.assertEqual(self.decode(raw + bytes(60000), [(0, len(raw) + 60000)], 0)[0], 0)
        tiny = b"hello hello hello hello"
        big = tiny + bytes(65536 - len(tiny))
        rc, out = self.decode(big, [(0, len(tiny)), (len(tiny), len(big) - len(tiny))], 2048)   # the second stream lies where the output ends: it needs the tail copy
        self.assertEqual((rc, out), (0, big))

    def test_corrupt_stream_fails(self):
        rnd = random.Random(5)
        raw = bytes(rnd.randrange(4) for _ in range(65536))
        data, padded = self.layout(raw, [(0, 65536)], 0)
        bad = bytearray(data)
        k = 12 + 8 + (len(raw) - padded) + 3
        bad[k] ^= 0xFF
        d = pathlib.Path(TMP.name)
        (d / "lz.bad").write_bytes(bytes(bad))
        r = run(build("t_lz"), d / "lz.bad", d / "lz.badout")
        out = (d / "lz.badout").read_bytes() if (d / "lz.badout").exists() else b""
        self.assertTrue(r.returncode != 0 or out != raw)


@unittest.skipUnless(CC, "no host C compiler")
class OpxTests(unittest.TestCase):
    def test_c_lookup_matches_the_python_model(self):
        rnd = random.Random(11)
        data = bytes(rnd.randrange(256) for _ in range(4096))
        ops = bytearray(data)
        for a, n in ((100, 20), (1000, 7), (1100, 40), (3000, 3)):
            for i in range(n):
                ops[a + i] ^= 0x5A
        rs = opx_store.diff_ranges(data, bytes(ops), pad=4)
        store = opx_store.build(rs, bytes(ops))
        d = pathlib.Path(TMP.name)
        (d / "opx.bin").write_bytes(store)
        (d / "data.bin").write_bytes(data)
        # every 4 byte access lies inside one range or outside all of them (a game pads its ranges so none straddles)
        addrs = [96, 100, 110, 119, 124, 200, 996, 1000, 1004, 1096, 1100, 1130, 2000, 2996, 3000, 0, 4000]
        r = run(build("t_opx", ["saturn/rt/sat_opx.c"]), d / "opx.bin", d / "data.bin", *addrs)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()

        def eff(x):
            v = opx_store.lookup(store, x)
            return data[x] if v is None else v

        hits = 0
        for line, a in zip(lines, addrs):
            f = line.split()
            self.assertEqual(int(f[1], 16), eff(a), f"byte at {a}")
            self.assertEqual(int(f[2], 16), eff(a) << 8 | eff(a + 1), f"word at {a}")
            self.assertEqual(int(f[3], 16), eff(a) << 24 | eff(a + 1) << 16 | eff(a + 2) << 8 | eff(a + 3), f"long at {a}")
            hits += int(f[4])
        self.assertGreater(hits, 8)                      # the changed bytes really come from the store
        self.assertTrue(all(int(l.split()[4]) == 0 for l, a in zip(lines, addrs) if a in (0, 124, 200, 2000, 4000)))
        self.assertEqual(lines[-1], f"flat {data[2] << 8 | data[3]:04x}")


if __name__ == "__main__":
    unittest.main()
