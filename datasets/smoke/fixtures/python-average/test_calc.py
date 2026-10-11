import unittest

from calc import average, normalize_port


class CalcTests(unittest.TestCase):
    def test_average_keeps_fraction(self):
        self.assertEqual(average([1, 2, 2]), 5 / 3)

    def test_average_empty_is_zero(self):
        self.assertEqual(average([]), 0)

    def test_normalize_port_adds_colon(self):
        self.assertEqual(normalize_port("3000"), ":3000")


if __name__ == "__main__":
    unittest.main()
