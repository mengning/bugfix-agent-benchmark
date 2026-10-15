import unittest

from cache import PermissionCache


class CacheTests(unittest.TestCase):
    def test_does_not_share_permissions_across_tenants(self):
        cache = PermissionCache()
        fetch = lambda tenant, resource: tenant == "tenant-a"
        self.assertTrue(cache.get("tenant-a", "record-1", fetch))
        self.assertFalse(cache.get("tenant-b", "record-1", fetch))

    def test_reuses_same_tenant_result(self):
        cache = PermissionCache()
        calls = []

        def fetch(tenant, resource):
            calls.append((tenant, resource))
            return True

        self.assertTrue(cache.get("tenant-a", "record-1", fetch))
        self.assertTrue(cache.get("tenant-a", "record-1", fetch))
        self.assertEqual([("tenant-a", "record-1")], calls)

    def test_fetches_other_resource(self):
        cache = PermissionCache()
        fetch = lambda tenant, resource: resource == "record-1"
        self.assertTrue(cache.get("tenant-a", "record-1", fetch))
        self.assertFalse(cache.get("tenant-a", "record-2", fetch))
