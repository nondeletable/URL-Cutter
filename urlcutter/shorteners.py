"""TinyURL shortener core with dual backend:
- direct HTTP API (DI via _get for unit tests)
- pyshorteners + ThreadPoolExecutor (keeps legacy tests happy)
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from http import HTTPStatus

# stdlib
from urllib.parse import quote, urlparse

import requests

# 3rd party
# local
from urlcutter import normalize_url

__all__ = ["shorten_via_tinyurl_core"]

DEFAULT_HTTP_TIMEOUT = 5


try:
    import pyshorteners
except Exception:
    pyshorteners = None


def _looks_like_url(s: str) -> bool:
    p = urlparse(s)
    return p.scheme in ("http", "https") and bool(p.netloc)


def shorten_via_tinyurl_core(
    url: str,
    timeout: float | None = None,
    *,
    _get: Callable[..., object] | None = None,
    _shortener_factory: Callable[[], object] | None = None,
    _pool_factory: Callable[..., ThreadPoolExecutor] | None = None,
) -> str:
    """Return a TinyURL short link for `url`.

    Behavior:
      - If `_get` is provided, use direct HTTP API (TinyURL endpoint).
      - Otherwise use `pyshorteners.Shortener().tinyurl.short(...)`.
      - If `timeout` is provided in the pyshorteners path, call via a pool and
        pass the timeout to `future.result(timeout=...)`.

    Raises:
      ValueError   — bad input, or provider returned non‑URL payload.
      TimeoutError — when pyshorteners path exceeds the given timeout.
      RuntimeError — network/provider errors in other cases.
    """
    # --- Early validate user input (before any provider call) ---
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a non-empty string")

    # 1) Normalize (trim spaces, validate scheme, etc.)
    norm = normalize_url(url)

    # --- A) Direct HTTP path (used by new unit-tests) ---
    if _get is not None:
        get = _get or requests.get
        api = f"https://tinyurl.com/api-create.php?url={quote(norm, safe='')}"
        try:
            resp = get(api, timeout=(timeout or DEFAULT_HTTP_TIMEOUT))
        except Exception as e:
            raise RuntimeError(f"TinyURL request failed: {e}") from e

        if getattr(resp, "status_code", HTTPStatus.OK) != HTTPStatus.OK:
            raise RuntimeError(f"TinyURL HTTP {resp.status_code}")

        short = getattr(resp, "text", "").strip()
        if not _looks_like_url(short):
            raise ValueError("TinyURL returned invalid payload")
        return short

    # --- B) pyshorteners + thread pool (legacy tests expect this) ---
    try:
        shortener_factory = _shortener_factory
        if shortener_factory is None:
            if pyshorteners is None:
                raise RuntimeError("pyshorteners is required for TinyURL but is not installed.")
            shortener_factory = pyshorteners.Shortener

        shortener = shortener_factory()
        tiny = shortener.tinyurl

        if timeout is None:
            return tiny.short(norm)

        pool_factory = _pool_factory or ThreadPoolExecutor
        with pool_factory(max_workers=1) as pool:
            fut = pool.submit(partial(tiny.short, norm))
            return fut.result(timeout=timeout)

    except TimeoutError:
        # Propagate exactly as tests expect
        raise
    except ValueError:
        # Respect provider's own ValueError if any
        raise
    except Exception as e:
        # Any other provider/pool error → RuntimeError
        raise RuntimeError(f"TinyURL provider error: {e}") from e
