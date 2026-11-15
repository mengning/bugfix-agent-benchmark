from collections.abc import Callable


class PermissionCache:
    def __init__(self) -> None:
        self._entries: dict[str, bool] = {}

    def get(self, tenant_id: str, resource_id: str, fetch: Callable[[str, str], bool]) -> bool:
        if resource_id not in self._entries:
            self._entries[resource_id] = fetch(tenant_id, resource_id)
        return self._entries[resource_id]
