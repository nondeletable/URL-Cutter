from concurrent.futures import TimeoutError

import pytest

from lite_upgrade import shorten_via_tinyurl


def test_shorten_via_tinyurl_happy_path(monkeypatch, fake_shortener_ok_factory):
    # было: monkeypatch.setattr("pyshorteners.Shortener", lambda: FakeShortener)
    # стало: подсовываем нашу фабрику (нулеарг. callable)
    monkeypatch.setattr("pyshorteners.Shortener", fake_shortener_ok_factory)

    result = shorten_via_tinyurl("https://example.com", timeout=1.0)
    assert result == "https://tiny.one/abc123"


def test_shorten_via_tinyurl_timeout(monkeypatch, fake_pool_timeout_factory, fake_shortener_ok_factory):
    monkeypatch.setattr("lite_upgrade.ThreadPoolExecutor", fake_pool_timeout_factory)
    monkeypatch.setattr("pyshorteners.Shortener", fake_shortener_ok_factory)

    with pytest.raises(TimeoutError):
        shorten_via_tinyurl("https://example.com", timeout=0.01)


def test_shorten_via_tinyurl_provider_error(monkeypatch, fake_shortener_boom_factory):
    monkeypatch.setattr("pyshorteners.Shortener", fake_shortener_boom_factory)

    with pytest.raises(RuntimeError) as excinfo:
        shorten_via_tinyurl("https://example.com", timeout=1.0)
    assert "boom" in str(excinfo.value)


@pytest.mark.parametrize(
    "bad_input",
    [
        "",  # пустая строка
        "   ",  # только пробелы
        None,  # None
        "not a url",  # мусор
        "ftp://example",  # не-HTTP(S) схема
    ],
)
def test_shorten_via_tinyurl_invalid_input_raises(monkeypatch, fake_shortener_assert_not_called_factory, bad_input):
    # Подсовываем провайдер, который упадёт, если его вдруг вызовут
    monkeypatch.setattr("pyshorteners.Shortener", fake_shortener_assert_not_called_factory)

    with pytest.raises(ValueError):
        shorten_via_tinyurl(bad_input, timeout=0.1)


# strip() действительно работает
def test_shorten_via_tinyurl_strips_spaces(monkeypatch, fake_shortener_ok_factory):
    monkeypatch.setattr("pyshorteners.Shortener", fake_shortener_ok_factory)
    res = shorten_via_tinyurl("   https://example.com/page  ", timeout=0.5)
    assert res == "https://tiny.one/abc123"


# В провайдер уходит уже очищенный URL (без пробелов)
def test_shorten_via_tinyurl_passes_clean_url_to_provider(monkeypatch, fake_shortener_expect_url_factory):
    expected = "https://example.com/x"
    # подсовываем провайдер, который сам проверит входной url
    monkeypatch.setattr("pyshorteners.Shortener", lambda: fake_shortener_expect_url_factory(expected))
    out = shorten_via_tinyurl("   https://example.com/x   ", timeout=0.5)
    assert out == "https://tiny.one/abc123"


# Поддерживаются и http, и https
@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/a",
        "https://example.com/b",
    ],
)
def test_shorten_via_tinyurl_accepts_http_and_https(monkeypatch, fake_shortener_ok_factory, url):
    monkeypatch.setattr("pyshorteners.Shortener", fake_shortener_ok_factory)
    out = shorten_via_tinyurl(url, timeout=0.2)
    assert out == "https://tiny.one/abc123"


# timeout из функции действительно прокидывается в future.result(timeout=...)
def test_shorten_via_tinyurl_forwards_timeout(
    monkeypatch, fake_pool_capturing_timeout_factory, fake_shortener_ok_factory
):
    # 1) ставим успешный провайдер
    monkeypatch.setattr("pyshorteners.Shortener", fake_shortener_ok_factory)

    # 2) подменяем пул на нашу реализацию, которая запоминает timeout
    fake_pool, captured = fake_pool_capturing_timeout_factory()
    monkeypatch.setattr("lite_upgrade.ThreadPoolExecutor", lambda max_workers=1: fake_pool)

    # 3) вызываем с «нестандартным» таймаутом и проверяем, что он дошёл
    t = 0.123
    out = shorten_via_tinyurl("https://example.com", timeout=t)
    assert out == "https://tiny.one/abc123"
    assert captured["timeout"] == t
    assert captured["calls"] == 1


def test_shorten_via_tinyurl_returns_provider_output(monkeypatch):
    # Провайдер вернёт нестандартный короткий URL — проверим, что функция не трогает его
    class FakeTiny:
        def short(self, url: str) -> str:
            return "https://tiny.one/custom123?x=1#frag"

    class FakeShortener:
        tinyurl = FakeTiny()

    monkeypatch.setattr("pyshorteners.Shortener", lambda: FakeShortener())

    out = shorten_via_tinyurl("https://example.com/abc", timeout=0.2)
    assert out == "https://tiny.one/custom123?x=1#frag"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/привет",
        "https://пример.рф/страница",
    ],
)
def test_shorten_via_tinyurl_handles_unicode(monkeypatch, fake_shortener_ok_factory, url):
    monkeypatch.setattr("pyshorteners.Shortener", fake_shortener_ok_factory)
    out = shorten_via_tinyurl(url, timeout=0.2)
    assert out == "https://tiny.one/abc123"
