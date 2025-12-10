from urllib.parse import urlparse

import pytest

from lite_upgrade import shorten_via_tinyurl


class DummyResp:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


# 1) Успех: провайдер вернул корректную короткую ссылку
def test_tinyurl_success():
    def fake_get(url, timeout=None):
        # Проверим, что мы вообще зовём API TinyURL с параметром url=
        assert "api" in url.lower() and "url=" in url
        return DummyResp(200, "https://tinyurl.com/abcd1")

    out = shorten_via_tinyurl("https://example.com/page", _get=fake_get)
    assert out == "https://tinyurl.com/abcd1"
    parsed = urlparse(out)
    assert parsed.scheme in ("http", "https") and parsed.netloc


# 2) HTTP-ошибка
def test_tinyurl_http_error():
    def fake_get(url, timeout=None):
        return DummyResp(503, "Service Unavailable")

    with pytest.raises(RuntimeError):
        shorten_via_tinyurl("https://example.com", _get=fake_get)


# 3) Битый ответ (не URL)
def test_tinyurl_bad_payload():
    def fake_get(url, timeout=None):
        return DummyResp(200, "NOT_A_URL")

    with pytest.raises(ValueError):
        shorten_via_tinyurl("https://example.com", _get=fake_get)


# 4) Таймаут/исключение на запросе
def test_tinyurl_timeout():
    class Boom(Exception):
        pass

    def fake_get(url, timeout=None):
        raise Boom("timeout")

    with pytest.raises(RuntimeError):
        shorten_via_tinyurl("https://example.com", _get=fake_get)


# 5) Заодно зафиксируем, что кривые схемы отфутболиваются (если внутри вызывается normalize_url)
def test_tinyurl_rejects_bad_scheme():
    def fake_get(url, timeout=None):
        # До сюда не должны дойти
        raise AssertionError("should fail earlier on normalize_url")

    with pytest.raises(ValueError):
        shorten_via_tinyurl("htp://bad", _get=fake_get)
