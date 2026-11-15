import json
import pathlib
import tempfile
import unittest

import _util  # noqa: F401
import loader_replay as lr


def make(stage, groups=None):
    d = pathlib.Path(tempfile.mkdtemp())
    (d / "a.bin").write_bytes(bytes(range(1, 33)))
    (d / "b.bin").write_bytes(bytes(range(101, 133)))
    plan = {"memory_size": 512, "stage": stage,
            "regions": [{"file": "a.bin", "offset": 0, "length": 32, "dest": 0},
                        {"file": "b.bin", "offset": 0, "length": 16, "dest": 100},
                        {"file": "b.bin", "offset": 16, "length": 16, "dest": 200}]}
    if groups is not None:
        plan["groups"] = groups
    (d / "plan.json").write_text(json.dumps(plan))
    return d


class ReplayTest(unittest.TestCase):
    def run_plan(self, d, *extra):
        return lr.main([str(d / "plan.json"), "--auto-group", *extra])

    def test_clean_coalescing_matches_sequential(self):
        d = make(stage=300)
        plan, data = lr.load_plan(d / "plan.json", None)
        ref, mem, seq_reads, reads = lr.replay(plan, data, lr.auto_groups(plan["regions"], 1 << 20))
        self.assertEqual((seq_reads, reads), (3, 2))   # the two neighbouring reads of b.bin became one
        self.assertEqual(lr.compare(plan, ref, mem)[0], [])
        self.assertEqual(self.run_plan(d), 0)

    def test_staging_over_loaded_data_is_caught(self):
        d = make(stage=0)   # the staging area sits on region 0, which is already loaded
        plan, data = lr.load_plan(d / "plan.json", None)
        ref, mem, _, _ = lr.replay(plan, data, lr.auto_groups(plan["regions"], 1 << 20))
        self.assertEqual(lr.compare(plan, ref, mem)[0], [0])
        self.assertEqual(self.run_plan(d), 1)

    def test_explicit_groups(self):
        d = make(stage=300, groups=[[1, 2]])
        self.assertEqual(lr.main([str(d / "plan.json")]), 0)

    def test_bad_input(self):
        d = make(stage=300)
        self.assertEqual(lr.main([str(d / "missing.json")]), 2)
        (d / "a.bin").unlink()
        self.assertEqual(lr.main([str(d / "plan.json")]), 2)


class ChecksumTest(unittest.TestCase):
    def test_rotating_xor_cancels_over_overlap_and_multiplicative_does_not(self):
        # Two regions overlap on bytes 32..63. A corrupt image differs from the reference only there.
        regions = [{"dest": 0, "length": 64}, {"dest": 32, "length": 64}]
        ref = bytearray(range(100))
        bad = bytearray(ref)
        for i in range(32, 64):
            bad[i] ^= 0x5A
        self.assertNotEqual(ref, bad)
        self.assertEqual(lr.checksum(ref, 0, regions, "xor"), lr.checksum(bad, 0, regions, "xor"))   # blind
        self.assertNotEqual(lr.checksum(ref, 0, regions, "mul"), lr.checksum(bad, 0, regions, "mul"))   # sees it

    def test_both_see_corruption_outside_the_overlap(self):
        regions = [{"dest": 0, "length": 64}, {"dest": 32, "length": 64}]
        ref = bytearray(range(100))
        bad = bytearray(ref)
        bad[5] ^= 1
        for algo in ("xor", "mul"):
            self.assertNotEqual(lr.checksum(ref, 0, regions, algo), lr.checksum(bad, 0, regions, algo))


if __name__ == "__main__":
    unittest.main()
