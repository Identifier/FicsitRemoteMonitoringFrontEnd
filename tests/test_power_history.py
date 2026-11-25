import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import server


class PowerHistoryTests(unittest.TestCase):
    def test_downsampling_preserves_missing_periods(self):
        history = server.History()
        values = [1, 2, 3, 4, 0, 0, 0, 0, 0]
        history.power = [[100000 + i * 5 + (600 if i >= 1 else 0), {"1": values}] for i in range(1440)]
        with patch("server.time.time", return_value=history.power[-1][0]):
            data = history.power_json(1440)
        self.assertEqual(data["coverage"]["all"][:2], [[99997.5, 100002.5], [100602.5, 107800]])
        self.assertEqual(data["coverage"]["groups"]["1"], data["coverage"]["all"])
        self.assertEqual(data["t"][:2], [100000, 100605])

    def test_grid_missing_while_another_grid_is_recorded(self):
        history = server.History()
        values = [1, 2, 3, 4, 0, 0, 0, 0, 0]
        history.power = [[100000 + i * 5, {"1": values, **({"2": values} if i != 1 else {})}] for i in range(1440)]
        with patch("server.time.time", return_value=history.power[-1][0]):
            data = history.power_json(1440)
        self.assertEqual(len(data["coverage"]["all"]), 1)
        self.assertEqual(data["coverage"]["groups"]["2"][:2], [[99997.5, 100002.5], [100007.5, 107200]])
        index = data["t"].index(100005)
        self.assertIsNone(data["groups"]["2"]["prod"][index])


if __name__ == "__main__":
    unittest.main()
