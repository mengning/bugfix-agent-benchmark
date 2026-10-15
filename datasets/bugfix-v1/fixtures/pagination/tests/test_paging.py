import unittest

from paging import page_slice


class PagingTests(unittest.TestCase):
    def test_full_pages_do_not_overlap(self):
        items = ["a", "b", "c", "d", "e"]
        self.assertEqual(["a", "b"], page_slice(items, 1, 2))
        self.assertEqual(["c", "d"], page_slice(items, 2, 2))

    def test_empty_result(self):
        self.assertEqual([], page_slice([], 1, 2))

    def test_invalid_arguments(self):
        with self.assertRaises(ValueError):
            page_slice([1, 2], 0, 2)
        with self.assertRaises(ValueError):
            page_slice([1, 2], 1, 0)
