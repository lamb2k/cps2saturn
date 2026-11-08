import unittest

import _util  # noqa: F401
import page_plan


class PagePlanTest(unittest.TestCase):
    def test_shared_restore_and_drops(self):
        census = {
            "stages": {
                "02": {"pages": [1, 2, 9], "keys": {"0x10": 1000, "0x11": 1, "0x12": 500}, "room": 2},
                "04": {"pages": [1, 3], "keys": {"0x20": 5}},
                "06": {"pages": [1, 2], "keys": {}},
            },
            "spill": {"04": [9, 2]},
        }
        p = page_plan.plan(census, shared_min=2)
        self.assertEqual(p["shared_pages"], [1, 2])
        s02 = p["stages"]["02"]
        self.assertEqual(s02["restore_pages"], [2, 9])
        self.assertEqual(s02["dropped_keys"], [0x11])
        self.assertEqual(p["stages"]["04"]["own_spill_on_kept_page"], [2])


if __name__ == "__main__":
    unittest.main()
