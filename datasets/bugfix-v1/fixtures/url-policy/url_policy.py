from urllib.parse import urlsplit


def is_allowed_url(url: str, allowed_domain: str) -> bool:
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return False
    if not host:
        return False
    return host.endswith(allowed_domain)
