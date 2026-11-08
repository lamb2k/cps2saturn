import unittest

import _util  # noqa: F401

try:
    import numpy as np
    import audio_compare
    HAVE = True
except ImportError:
    HAVE = False


@unittest.skipUnless(HAVE, "numpy not installed")
class AudioCompareTest(unittest.TestCase):
    def test_delayed_copy_matches(self):
        rng = np.random.default_rng(1)
        rate = 44100
        env = np.repeat(rng.uniform(0, 1, 40) > 0.5, rate // 4).astype(np.float32)
        tone = (np.sin(np.arange(len(env)) * 0.05) * 8000 * env).astype(np.float32)
        ref = np.stack([tone, tone], axis=1)
        cap = np.concatenate([np.zeros((rate // 2, 2), np.float32), ref])
        r = audio_compare.compare(ref, cap)
        self.assertAlmostEqual(r["offset_s"], 0.5, places=2)
        self.assertGreater(r["envelope_corr"], 0.99)
        self.assertLess(abs(r["level_db"]), 0.5)


if __name__ == "__main__":
    unittest.main()
