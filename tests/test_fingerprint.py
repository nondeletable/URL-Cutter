import pytest

from lite_upgrade import _url_fingerprint

SHA1_MIN_LENGTH = 16


def test_url_fingerprint_basic():
    u = "https://example.com/a?b=1"
    out = _url_fingerprint(u)
    # теперь отпечаток — hex-строка
    assert isinstance(out, str)
    assert all(ch in "0123456789abcdef" for ch in out.lower())
    assert len(out) >= SHA1_MIN_LENGTH  # SHA1 = 40 символов


def test_url_fingerprint_differs_for_different_urls():
    u1 = "https://example.com/a"
    u2 = "https://example.com/b"
    assert _url_fingerprint(u1) != _url_fingerprint(u2)


def test_url_fingerprint_invalid_input_raises():
    with pytest.raises(ValueError):
        _url_fingerprint("htp://  ")


def test_url_fingerprint_stable_same_input():
    u = "https://example.com/path?q=1#frag"
    assert _url_fingerprint(u) == _url_fingerprint(u)
