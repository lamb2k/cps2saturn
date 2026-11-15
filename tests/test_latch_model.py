import unittest

import _util  # noqa: F401
import latch_model as m


class LatchModelTest(unittest.TestCase):
    def test_sequence_protocol_never_mixes(self):
        states, terminals, bad, _ = m.explore("sequence")
        self.assertEqual(bad, 0)
        self.assertGreater(terminals, 100)   # a real search, not a trivial one

    def test_naive_latch_mixes_old_and_new(self):
        _, _, bad, example = m.explore("naive")
        self.assertGreater(bad, 0)
        self.assertNotIn(example, m.records_for(3, 3))

    def test_check_and_retry_still_mixes(self):
        _, _, bad, _ = m.explore("retry")
        self.assertGreater(bad, 0)

    def test_cli(self):
        self.assertEqual(m.main(["--regs", "2", "--records", "2"]), 0)
        self.assertEqual(m.main(["--regs", "1"]), 2)


if __name__ == "__main__":
    unittest.main()
