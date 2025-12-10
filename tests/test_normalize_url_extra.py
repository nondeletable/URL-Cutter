import pytest

from lite_upgrade import normalize_url


@pytest.mark.parametrize(
    "src, expect",
    [
        # добавляет http если нет схемы, приводит хост к lower, убирает fragment
        ("Example.COM", "http://example.com"),
        ("example.com/path#frag", "http://example.com/path"),
        # сохраняет https, нормализует путь, сортирует query (если так задумано)
        ("https://EXAMPLE.com/a?b=2&a=1", "https://example.com/a?a=1&b=2"),
        # стандартные порты убирает, нестандартные оставляет
        ("http://example.com:80/a", "http://example.com/a"),
        ("https://example.com:443", "https://example.com"),
        ("https://example.com:8443/x", "https://example.com:8443/x"),
        # пустой путь → '/'
        ("https://example.com", "https://example.com"),
    ],
)
def test_normalize_url_happy(src, expect):
    assert normalize_url(src) == expect


@pytest.mark.parametrize("bad", ["", "   ", "exa mple.com", "\t\texample.com"])
def test_normalize_url_spaces_or_empty(bad):
    with pytest.raises(ValueError):
        normalize_url(bad)


@pytest.mark.parametrize("bad", ["ftp://example.com", "htp://example.com", "mailto:a@b"])
def test_normalize_url_bad_scheme(bad):
    with pytest.raises(ValueError):
        normalize_url(bad)
