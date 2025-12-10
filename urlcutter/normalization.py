import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

HTTP_DEFAULT_PORT = 80
HTTPS_DEFAULT_PORT = 443


def _url_fingerprint(url: str) -> str:
    if url is None:
        raise ValueError("url is required")
    s = str(url).strip()
    if not s:
        raise ValueError("url is empty")

    # использовать normalize_url ниже
    s = normalize_url(s)

    digest = hashlib.sha1(s.encode("utf-8")).hexdigest()
    return digest


def normalize_url(s: str) -> str:
    s = str(s)
    s = s.strip(" ")
    if not s:
        raise ValueError("empty url")

    if any(ch.isspace() for ch in s):
        raise ValueError("spaces in url")

    parts = urlsplit(s)
    scheme = parts.scheme.lower()

    if scheme:
        if scheme not in {"http", "https"}:
            raise ValueError("bad scheme")
    else:
        parts = urlsplit("http://" + s)
        scheme = "http"

    hostname = (parts.hostname or "").lower()
    port = parts.port
    if port and (
        (scheme == "http" and port == HTTP_DEFAULT_PORT) or (scheme == "https" and port == HTTPS_DEFAULT_PORT)
    ):
        netloc = hostname
    else:
        netloc = hostname if port is None else f"{hostname}:{port}"

    path = parts.path or ""

    if parts.query:
        q = parse_qsl(parts.query, keep_blank_values=True)
        q.sort()
        query = urlencode(q)
    else:
        query = ""

    fragment = ""
    return urlunsplit((scheme, netloc, path, query, fragment))
