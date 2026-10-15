import unittest

from url_policy import is_allowed_url


class UrlPolicyTests(unittest.TestCase):
    def test_rejects_suffix_spoof(self):
        self.assertFalse(is_allowed_url("https://evil-example.com/private", "example.com"))
        self.assertFalse(is_allowed_url("https://notexample.com/private", "example.com"))

    def test_allows_exact_and_subdomain(self):
        self.assertTrue(is_allowed_url("https://example.com/home", "example.com"))
        self.assertTrue(is_allowed_url("https://api.example.com/home", "example.com"))

    def test_rejects_malformed_url(self):
        self.assertFalse(is_allowed_url("not a URL", "example.com"))
