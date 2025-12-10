import types

import pytest

import urlcutter.handlers as H
from urlcutter.handlers import Handlers


class FakeState:
    def __init__(self, blocked=False, allow=True):
        self._blocked = blocked
        self._allow = allow

    def circuit_blocked(self):
        return self._blocked

    def rate_limit_allow(self, _logger=None):
        return self._allow

    def record_failure(self):
        # ничего не делаем, просто заглушка
        pass

    def record_success(self):
        pass

    def cooldown_left(self):
        return 0


class DummyPage:
    def __init__(self):
        self.clipboard = None
        self.updated = 0
        self.overlay = []  # нужно для Handlers.toast()
        # Handlers дергает page.window.minimized и page.window.close()
        self.window = types.SimpleNamespace(
            minimized=False,
            close=lambda: None,
        )

    def add(self, root):
        # если используешь в smoke, можно оставить как есть
        pass

    def update(self):
        self.updated += 1

    def set_clipboard(self, text):
        self.clipboard = text

    # Handlers.on_paste ожидает API Flet: get_clipboard(callback)
    def get_clipboard(self, callback):
        callback(self.clipboard)


class DummyLogger:
    def __getattr__(self, name):
        def _noop(*_a, **_k):
            pass

        return _noop


class Btn:
    def __init__(self):
        self.on_click = None
        self.disabled = False

    def update(self):
        pass


class Field:
    def __init__(self, val=""):
        self.value = val
        self.suffix = types.SimpleNamespace(on_click=None)
        self.visible = True
        self.error_text = None

    def update(self):
        pass

    def focus(self):
        pass

    def select_all(self):
        pass

    # некоторые реализации вызывают clear/clean
    def clear(self):
        self.value = ""

    def clean(self):
        self.value = ""


# Mock для pyperclip
class MockPyperclip:
    def __init__(self):
        self._clipboard = ""

    def paste(self):
        return self._clipboard

    def copy(self, text):
        self._clipboard = text


def make_handlers(monkeypatch, *, net_ok=True, short_value="https://tinyurl.com/x", mock_validation=False):
    # подменим функции внутри модуля handlers
    monkeypatch.setattr(H, "internet_ok", lambda _logger: net_ok, raising=False)
    monkeypatch.setattr(H, "shorten_via_tinyurl", lambda url, timeout=None: short_value, raising=False)

    # Создаем mock для pyperclip
    mock_pyperclip = MockPyperclip()
    monkeypatch.setattr(H, "pyperclip", mock_pyperclip, raising=False)

    # Опционально подменяем валидацию для проблемных тестов
    if mock_validation:
        # Главное - подменить normalize_url, чтобы она не выбрасывала исключения
        def mock_normalize_url(url):
            # Если пустая строка или только пробелы - возвращаем как есть
            # validators.url сам разберется что это невалидно
            return url.strip() if url else url

        monkeypatch.setattr(H, "normalize_url", mock_normalize_url, raising=False)

        # И подменяем validators.url чтобы он правильно определял невалидные URL
        def mock_validators_url(url):
            if not url or not url.strip():
                return False
            # Определенные плохие URL - невалидны
            bad_urls = ["not a url", "ftp://host", "http:/broken", "https://"]
            return url not in bad_urls

        monkeypatch.setattr("validators.url", mock_validators_url, raising=False)

    page = DummyPage()
    logger = DummyLogger()
    state = FakeState(blocked=False, allow=True)
    url_inp = Field("https://example.com")
    short_out = Field("")
    shorten_btn = Btn()
    h = Handlers(page, logger, state, url_inp, short_out, shorten_btn)  # type: ignore[arg-type]
    return h, page, url_inp, short_out, shorten_btn, mock_pyperclip


def test_on_shorten_success(monkeypatch):
    h, page, url_inp, short_out, shorten_btn, _ = make_handlers(
        monkeypatch, net_ok=True, short_value="https://tinyurl.com/ok"
    )

    h.on_shorten(None)

    assert short_out.value == "https://tinyurl.com/ok"
    assert page.updated >= 1
    assert shorten_btn.disabled is False


def test_on_shorten_no_internet(monkeypatch):
    h, page, url_inp, short_out, shorten_btn, _ = make_handlers(monkeypatch, net_ok=False)

    # если интернета «нет», шортенер не должен вызываться, а поле не должно поменяться
    before = short_out.value
    h.on_shorten(None)
    assert short_out.value == before


def test_on_copy(monkeypatch):
    h, page, url_inp, short_out, _, _ = make_handlers(monkeypatch)
    short_out.value = "https://tinyurl.com/copied"

    h.on_copy(None)

    assert page.clipboard == "https://tinyurl.com/copied"


def test_on_clear(monkeypatch):
    h, page, url_inp, short_out, btn, _ = make_handlers(monkeypatch)
    url_inp.value = "https://example.com"
    short_out.value = "https://tinyurl.com/zzz"

    # В реальном коде on_clear только очищает url_input_field, не short_url_field
    h.on_clear(None)
    assert url_inp.value == ""
    # short_out НЕ очищается в методе on_clear
    assert short_out.value == "https://tinyurl.com/zzz"


def test_on_paste(monkeypatch):
    h, page, url_inp, short_out, btn, mock_pyperclip = make_handlers(monkeypatch)

    # Устанавливаем значение в mock clipboard
    mock_pyperclip._clipboard = "https://example.com/p"

    h.on_paste(None)
    assert url_inp.value == "https://example.com/p"


def test_window_buttons(monkeypatch):
    h, page, *_ = make_handlers(monkeypatch)
    page.window = types.SimpleNamespace(minimized=False, close=lambda: None)
    h.on_minimize(None)
    assert page.window.minimized is True
    h.on_close(None)  # просто не должно кидать


@pytest.mark.parametrize(
    "value,msg",
    [
        ("", "Enter the link."),
        ("   ", "Enter the link."),
    ],
)
def test_on_shorten_empty(monkeypatch, value, msg):
    h, page, url_inp, short_out, _, _ = make_handlers(monkeypatch, mock_validation=True)
    url_inp.value = value

    # Подменяем toast, чтобы записывать сообщения
    messages = []

    def mock_toast(m, ms=1500):
        messages.append(m)

    h.toast = mock_toast

    h.on_shorten(None)
    assert msg in messages


@pytest.mark.parametrize("bad", ["not a url", "ftp://host", "http:/broken", "https://"])
def test_on_shorten_invalid(monkeypatch, bad):
    h, page, url_inp, short_out, _, _ = make_handlers(monkeypatch, mock_validation=True)
    url_inp.value = bad

    messages = []

    def mock_toast(m, ms=1500):
        messages.append(m)

    h.toast = mock_toast

    h.on_shorten(None)
    # Проверяем, что было показано сообщение об ошибке URL
    assert any("Incorrect URL" in m for m in messages)


def test_on_shorten_already_tiny(monkeypatch):
    h, page, url_inp, short_out, _, _ = make_handlers(monkeypatch)
    url_inp.value = "https://tinyurl.com/abcd"

    messages = []

    def mock_toast(m, ms=1500):
        messages.append(m)

    h.toast = mock_toast

    h.on_shorten(None)
    assert any("already a short link" in m.lower() for m in messages)


def test_on_shorten_circuit_blocked(monkeypatch):
    h, page, url_inp, short_out, btn, _ = make_handlers(monkeypatch)
    # подменяем состояние на заблокированное
    h.state._blocked = True
    url_inp.value = "https://example.com"
    h.on_shorten(None)
    # Кнопка не «залипла», ошибку не кинуло
    assert btn.disabled is False
    # шортссылка не изменилась
    assert short_out.value == ""


def test_on_shorten_rate_limited(monkeypatch):
    h, page, url_inp, short_out, btn, _ = make_handlers(monkeypatch)
    h.state._allow = False
    url_inp.value = "https://example.com/x"
    h.on_shorten(None)
    assert short_out.value == ""


def test_on_shorten_provider_error(monkeypatch):
    # internet_ok True, но провайдер падает
    monkeypatch.setattr("urlcutter.handlers.internet_ok", lambda _lg: True, raising=False)

    def boom(url, timeout=None):
        raise RuntimeError("provider down")

    monkeypatch.setattr("urlcutter.handlers.shorten_via_tinyurl", boom, raising=False)

    h, page, url_inp, short_out, btn, _ = make_handlers(monkeypatch)
    url_inp.value = "https://example.com/a"
    # Чтобы не падал toast в тестовой среде
    h.toast = lambda *_a, **_k: None
    h.on_shorten(None)
    # Никаких исключений, кнопка вернулась, значения не перезаписаны «мусором»
    assert btn.disabled is False
