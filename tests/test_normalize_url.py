import pytest

from lite_upgrade import normalize_url


def test_normalize_adds_scheme_and_trims_spaces():
    out = normalize_url("  example.com  ")
    assert out == "http://example.com"


def test_normalize_lowercases_scheme_and_host():
    out = normalize_url("HTTPS://ExAmPle.COM/Path")
    assert out == "https://example.com/Path"


def test_normalize_rejects_internal_spaces():
    with pytest.raises(ValueError):
        normalize_url("https://exa mple.com")


def test_normalize_rejects_empty():
    with pytest.raises(ValueError):
        normalize_url("")


def test_normalize_unicode_domain_stays_as_is():
    out = normalize_url("https://пример.рф/страница")
    assert out == "https://пример.рф/страница"
