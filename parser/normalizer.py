import logging
from typing import Optional, Set
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

logger: logging.Logger = logging.getLogger("app.parser.normalizer")

ALLOWED_DOMAINS: Set[str] = {
    "olx.ua",
    "www.olx.ua",
    "olx.pl",
    "www.olx.pl",
    "olx.kz",
    "www.olx.kz",
    "olx.ro",
    "www.olx.ro",
    "olx.pt",
    "www.olx.pt",
    "olx.bg",
    "www.olx.bg",
    "olx.uz",
    "www.olx.uz",
}


def normalize_url(raw_url: str) -> Optional[str]:
    try:
        clean_url: str = raw_url.strip()
        parsed = urlparse(clean_url)
        if not parsed.scheme or parsed.scheme not in {"http", "https"}:
            return None

        hostname: Optional[str] = parsed.netloc.lower()
        if not hostname or hostname not in ALLOWED_DOMAINS:
            return None

        path: str = parsed.path
        if path.startswith("/d/list/"):
            path = path.replace("/d/list/", "/list/", 1)
        elif path.startswith("/d/uk/"):
            path = path.replace("/d/uk/", "/uk/", 1)

        query_params = parse_qs(parsed.query)
        if "search[order]" not in query_params:
            query_params["search[order]"] = ["created_at:desc"]

        new_query = urlencode(query_params, doseq=True)
        normalized = urlunparse((parsed.scheme, hostname, path, parsed.params, new_query, parsed.fragment))
        return normalized
    except Exception as exc:
        logger.error("Failed to normalize URL '%s': %s", raw_url, exc, exc_info=True)
        return None


def to_absolute_url(base_url: str, target_path: str) -> str:
    try:
        if target_path.startswith("http://") or target_path.startswith("https://"):
            return target_path
        return urljoin(base_url, target_path)
    except Exception as exc:
        logger.error("Error making absolute URL from '%s' and '%s': %s", base_url, target_path, exc)
        return target_path