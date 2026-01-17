import webbrowser
from concurrent.futures import TimeoutError as FutTimeout
from datetime import UTC, datetime

import flet as ft
import pytest

from urlcutter.handlers import Handlers, _safe_fp


class FakeLogger:
    def __init__(self):
        self.messages = []

    def info(self, msg, *a):
        self.messages.append(("info", msg))

    def debug(self, msg, *a):
        self.messages.append(("debug", msg))

    def warning(self, msg, *a):
        self.messages.append(("warning", msg))

    def exception(self, msg, *a):
        self.messages.append(("exception", msg))

    def error(self, msg, *a):
        self.messages.append(("error", msg))


class FakePage:
    def __init__(self):
        self.overlay = []
        self.controls = []
        self.updated = False
        self.cursor = None
        self.window = type("W", (), {"close": lambda self: None, "minimized": False})()

    def update(self):
        self.updated = True

    def set_clipboard(self, text):
        self.clipboard = text


class FakeField:
    def __init__(self, value=""):
        self.value = value
        self.updated = False

    def update(self):
        self.updated = True


class FakeState:
    def __init__(self, blocked=False, allow=True, internet=True):
        self._blocked = blocked
        self._allow = allow
        self._internet = internet
        self.success = 0
        self.failure = 0

    def circuit_blocked(self):
        return self._blocked

    def cooldown_left(self):
        return 42

    def rate_limit_allow(self, logger):
        return self._allow

    def record_success(self):
        self.success += 1

    def record_failure(self):
        self.failure += 1


def test_safe_fp_returns_input_and_empty():
    # на нормальной строке должен вернуть непустую строку (фингерпринт)
    result = _safe_fp("abc")
    assert isinstance(result, str)
    assert result != ""

    # на пустой строке → "<empty>"
    assert _safe_fp("") == "<empty>"


def test_validate_dates():
    assert Handlers.validate_dates(None, None) is True
    now = datetime.now(UTC)
    assert Handlers.validate_dates(now, now) is True
    assert Handlers.validate_dates(now, now.replace(year=2100)) is True
    assert Handlers.validate_dates(now.replace(year=2100), now) is False


def test_fmt_local_dt_none_and_valid():
    h = Handlers(FakePage(), FakeLogger(), None, None, None, None)
    assert h._fmt_local_dt(None) == "—"
    dt = datetime(2025, 1, 1, tzinfo=UTC)
    result = h._fmt_local_dt(dt)
    assert "2025" in result


def test_on_clear_with_and_without_value():
    page = FakePage()
    field = FakeField("test")
    h = Handlers(page, FakeLogger(), None, field, None, None)

    h.on_clear(None)
    assert field.value == ""
    assert field.updated is True

    # повторный вызов — пустое поле
    field.value = ""
    h.on_clear(None)
    # должно появиться сообщение "Nothing to clear!"
    assert any(isinstance(ctrl, object) for ctrl in page.overlay)


def test_on_copy_with_and_without_value(monkeypatch):
    page = FakePage()
    field = FakeField("shorturl")
    h = Handlers(page, FakeLogger(), None, None, field, None)

    # подменим history.increment_copy_count, чтобы не ломать тест
    h.history.increment_copy_count = lambda _id: None
    h._last_history_id = 1

    h.on_copy(None)
    assert page.clipboard == "shorturl"

    # пустое значение
    field.value = ""
    h.on_copy(None)
    messages = [
        ctrl.content.value for ctrl in page.overlay if hasattr(ctrl, "content") and hasattr(ctrl.content, "value")
    ]
    assert "Nothing to copy!" in messages


def test_on_shorten_empty_input(monkeypatch):
    page = FakePage()
    field_in = FakeField("")  # пустое поле
    field_out = FakeField()
    h = Handlers(page, FakeLogger(), FakeState(), field_in, field_out, FakeField())

    h.on_shorten(None)

    # должен появиться toast с сообщением
    assert any("Enter the link." in getattr(ctrl.content, "value", "") for ctrl in page.overlay)


def test_on_shorten_invalid_url(monkeypatch):
    page = FakePage()
    field_in = FakeField("not a url")
    field_out = FakeField()
    h = Handlers(page, FakeLogger(), FakeState(), field_in, field_out, FakeField())

    h.on_shorten(None)
    assert any("Incorrect URL" in getattr(ctrl.content, "value", "") for ctrl in page.overlay)


def test_on_shorten_already_tinyurl(monkeypatch):
    page = FakePage()
    field_in = FakeField("https://tinyurl.com/abc")
    field_out = FakeField()
    h = Handlers(page, FakeLogger(), FakeState(), field_in, field_out, FakeField())

    h.on_shorten(None)
    assert any("already a short link" in getattr(ctrl.content, "value", "") for ctrl in page.overlay)


def test_on_shorten_blocked_by_state(monkeypatch):
    page = FakePage()
    field_in = FakeField("https://example.com")
    field_out = FakeField()
    state = FakeState(blocked=True)
    h = Handlers(page, FakeLogger(), state, field_in, field_out, FakeField())

    h.on_shorten(None)
    assert any("cooling down" in getattr(ctrl.content, "value", "") for ctrl in page.overlay)


def test_on_shorten_no_internet(monkeypatch):
    page = FakePage()
    field_in = FakeField("https://example.com")
    field_out = FakeField()
    state = FakeState()

    # патчим internet_ok → False
    monkeypatch.setattr("urlcutter.handlers.internet_ok", lambda logger: False)

    h = Handlers(page, FakeLogger(), state, field_in, field_out, FakeField())
    h.on_shorten(None)

    assert any("No internet" in getattr(ctrl.content, "value", "") for ctrl in page.overlay)


def test_on_shorten_success(monkeypatch):
    page = FakePage()
    field_in = FakeField("https://example.com")
    field_out = FakeField()
    state = FakeState()

    h = Handlers(page, FakeLogger(), state, field_in, field_out, FakeField())

    # патчим shorten_via_tinyurl → вернуть фиксированный результат
    monkeypatch.setattr("urlcutter.handlers.shorten_via_tinyurl", lambda url, timeout: "https://tiny.one/test123")

    # патчим history.add → возвращает объект с id
    class DummyStored:
        def __init__(self):
            self.id = 42

    monkeypatch.setattr(h.history, "add", lambda rec: DummyStored())

    h.on_shorten(None)

    # короткая ссылка должна появиться
    assert field_out.value == "https://tiny.one/test123"
    # появился toast с "Done!"
    assert any("Done!" in getattr(ctrl.content, "value", "") for ctrl in page.overlay)
    # state.record_success() должен сработать
    assert state.success == 1
    # _last_history_id обновился
    assert h._last_history_id == 42


def test_on_shorten_timeout(monkeypatch):
    page = FakePage()
    field_in = FakeField("https://example.com")
    field_out = FakeField()
    state = FakeState()
    h = Handlers(page, FakeLogger(), state, field_in, field_out, FakeField())

    monkeypatch.setattr("urlcutter.handlers.shorten_via_tinyurl", lambda url, t: (_ for _ in ()).throw(FutTimeout()))

    h.on_shorten(None)

    assert state.failure == 1
    assert any("did not respond" in getattr(ctrl.content, "value", "") for ctrl in page.overlay)


@pytest.mark.parametrize(
    "msg,expected",
    [
        ("429 Too Many Requests", "Too many requests"),
        ("503 Service Unavailable", "temporarily unavailable"),
        ("boom!", "Failed to shorten"),
    ],
)
def test_on_shorten_error_cases(monkeypatch, msg, expected):
    page = FakePage()
    field_in = FakeField("https://example.com")
    field_out = FakeField()
    state = FakeState()
    h = Handlers(page, FakeLogger(), state, field_in, field_out, FakeField())

    monkeypatch.setattr("urlcutter.handlers.shorten_via_tinyurl", lambda url, t: (_ for _ in ()).throw(Exception(msg)))

    h.on_shorten(None)

    assert state.failure == 1
    assert any(expected in getattr(ctrl.content, "value", "") for ctrl in page.overlay)


def test_save_and_back_view(monkeypatch):
    page = FakePage()
    main_body = FakeField("main content")
    main_container = type("C", (), {"content": main_body})()
    h = Handlers(page, FakeLogger(), None, None, None, None)
    h.attach_main_body(main_container)

    # сохраняем
    h._save_current_view()
    assert h._prev_view == main_body

    # восстанавливаем
    h._back_to_saved_view()
    assert main_container.content == main_body


def test_back_view_without_saved(monkeypatch):
    page = FakePage()
    h = Handlers(page, FakeLogger(), None, None, None, None)

    h._prev_view = None
    h._back_to_saved_view()
    # должно появиться сообщение "Nothing to go back to."
    assert any("Nothing to go back to." in getattr(ctrl.content, "value", "") for ctrl in page.overlay)


def test_on_open_history(monkeypatch):
    page = FakePage()
    h = Handlers(page, FakeLogger(), None, FakeField(), FakeField(), FakeField())
    h.attach_main_body(type("C", (), {"content": None})())

    # патчим make_history_screen
    called = {}
    monkeypatch.setattr("urlcutter.handlers.make_history_screen", lambda **kw: called.setdefault("ok", True) or "dummy")

    h.on_open_history()
    assert called.get("ok") is True
    assert h.main_body.content is not None


def test_on_close_and_minimize():
    page = FakePage()
    h = Handlers(page, FakeLogger(), None, None, None, None)

    # close
    h.on_close(None)  # просто проверим, что не падает

    # minimize
    h.on_minimize(None)
    assert page.window.minimized is True


def test_on_open_info_adds_dialog(monkeypatch):
    page = FakePage()
    h = Handlers(page, FakeLogger(), None, FakeField(), FakeField(), FakeField())

    h.on_open_info(None)

    # Проверяем, что в overlay появился AlertDialog
    dialogs = [ctrl for ctrl in page.overlay if isinstance(ctrl, ft.AlertDialog)]
    assert dialogs, "AlertDialog должен быть добавлен в overlay"

    dialog = dialogs[0]
    assert dialog.open is True
    assert isinstance(dialog.title, ft.Text)
    assert "ABOUT" in dialog.title.value


def test_back_to_saved_view_titlebar_error(monkeypatch):
    page = FakePage()
    h = Handlers(page, FakeLogger(), None, None, None, None)
    h.title_row, h.drag_area = object(), object()  # чтобы titlebar_set_main вызвался

    # патчим titlebar_set_main, чтобы кидал исключение
    monkeypatch.setattr(
        "urlcutter.handlers.titlebar_set_main", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("fail"))
    )

    # подготавливаем prev_view
    prev = FakeField("prev")
    h._prev_view = prev
    h.main_body = type("C", (), {"content": None})()

    h._back_to_saved_view()
    # несмотря на ошибку titlebar_set_main, prev должен восстановиться
    assert h.main_body.content == prev


def test_back_to_saved_view_fails(monkeypatch):
    page = FakePage()
    h = Handlers(page, FakeLogger(), None, None, None, None)

    # подменим main_body так, чтобы у него не было .content (сломаем on purpose)
    h._prev_view = "X"
    h.main_body = object()

    h._back_to_saved_view()
    # должно появиться сообщение "Back failed."
    assert any("Back failed." in getattr(ctrl.content, "value", "") for ctrl in page.overlay)


def test_on_shorten_unknown_error(monkeypatch):
    page = FakePage()
    field_in = FakeField("https://example.com")
    field_out = FakeField()
    state = FakeState()
    h = Handlers(page, FakeLogger(), state, field_in, field_out, FakeField())

    # shorten_via_tinyurl кидает непредсказуемую ошибку
    monkeypatch.setattr(
        "urlcutter.handlers.shorten_via_tinyurl", lambda url, t: (_ for _ in ()).throw(Exception("weird error"))
    )

    h.on_shorten(None)

    assert state.failure == 1
    assert any("Failed to shorten" in getattr(ctrl.content, "value", "") for ctrl in page.overlay)


def test_on_open_info_button_opens_link(monkeypatch):
    page = FakePage()
    h = Handlers(page, FakeLogger(), None, FakeField(), FakeField(), FakeField())

    opened = {}
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.setdefault("url", url))

    h.on_open_info(None)

    dialog = next(ctrl for ctrl in page.overlay if isinstance(ctrl, ft.AlertDialog))

    # Найдём Row с кнопками и первую ElevatedButton
    btn = None
    for ctrl in dialog.content.controls:
        if isinstance(ctrl, ft.Row):
            for c in ctrl.controls:
                if isinstance(c, ft.ElevatedButton):
                    btn = c
                    break
    assert btn is not None

    # Клик
    btn.on_click(None)

    assert opened.get("url") is not None
    assert ("http" in opened["url"]) or ("mailto:" in opened["url"])


def test_on_open_history_failure(monkeypatch):
    page = FakePage()
    h = Handlers(page, FakeLogger(), None, FakeField(), FakeField(), FakeField())
    h.attach_main_body(type("C", (), {"content": None})())

    monkeypatch.setattr(h.history, "list", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("db fail")))

    h.on_open_history()

    assert any("Failed to load history" in getattr(ctrl.content, "value", "") for ctrl in page.overlay)


def test_back_to_saved_view_logger_warning(monkeypatch):
    page = FakePage()
    logger = FakeLogger()
    h = Handlers(page, logger, None, None, None, None)

    # _prev_view отсутствует
    h._prev_view = None
    h._back_to_saved_view()

    # должен быть warning
    assert any("Back pressed" in msg for lvl, msg in logger.messages if lvl == "warning")


def test_on_shorten_logs_rate_and_unavailable(monkeypatch):
    page = FakePage()
    field_in = FakeField("https://example.com")
    field_out = FakeField()
    state = FakeState()
    h = Handlers(page, FakeLogger(), state, field_in, field_out, FakeField())

    # 429 → rate
    monkeypatch.setattr("urlcutter.handlers.shorten_via_tinyurl", lambda u, t: (_ for _ in ()).throw(Exception("429")))
    h.on_shorten(None)
    assert state.failure >= 1

    # 503 → unavailable
    monkeypatch.setattr("urlcutter.handlers.shorten_via_tinyurl", lambda u, t: (_ for _ in ()).throw(Exception("503")))
    h.on_shorten(None)
    assert state.failure >= 2


def test_on_copy_history_increment_fails(monkeypatch):
    page = FakePage()
    field = FakeField("shorturl")
    logger = FakeLogger()
    h = Handlers(page, logger, None, None, field, None)
    h._last_history_id = 1

    # подменим history.increment_copy_count так, чтобы он падал
    def bad_increment(_):
        raise RuntimeError("db error")

    h.history.increment_copy_count = bad_increment

    h.on_copy(None)

    # должен быть лог debug про ошибку
    assert any("History increment failed" in msg for lvl, msg in logger.messages if lvl == "debug")


def test_close_dialog_sets_open_false():
    page = FakePage()
    h = Handlers(page, FakeLogger(), None, None, None, None)

    dialog = type("D", (), {"open": True})()
    h.close_dialog(dialog)
    assert dialog.open is False


def test_save_current_view_fallback(monkeypatch):
    page = FakePage()
    logger = FakeLogger()
    h = Handlers(page, logger, None, None, None, None)

    # main_body отсутствует → пойдёт во fallback с page.controls
    page.controls = [FakeField("ctrl")]
    h._save_current_view()
    assert h._prev_view == page.controls[0]
    assert any("Saved prev view" in msg for lvl, msg in logger.messages if lvl == "debug")


def test_back_to_saved_view_restore_fail(monkeypatch):
    page = FakePage()
    logger = FakeLogger()
    h = Handlers(page, logger, None, None, None, None)

    # prev есть, но main_body = None → AttributeError
    h._prev_view = FakeField("prev")
    h.main_body = None

    h._back_to_saved_view()
    # должен быть лог exception + toast "Back failed."
    assert any("Back failed" in msg for lvl, msg in logger.messages if lvl == "exception")
    assert any("Back failed." in getattr(ctrl.content, "value", "") for ctrl in page.overlay)


def test_on_open_history_titlebar_set_back_fails(monkeypatch):
    page = FakePage()
    logger = FakeLogger()
    h = Handlers(page, logger, None, FakeField(), FakeField(), FakeField())
    h.attach_main_body(type("C", (), {"content": None})())

    # замокаем titlebar_set_back чтобы он падал
    monkeypatch.setattr(
        "urlcutter.handlers.titlebar_set_back", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("fail"))
    )

    # замокаем history.list чтобы вернуть пустой результат
    class DummyHP:
        total = 0
        items = []

    monkeypatch.setattr(h.history, "list", lambda *a, **kw: DummyHP())

    h.on_open_history()
    # должен быть лог debug про skip
    assert any("titlebar_set_back skipped" in msg for lvl, msg in logger.messages if lvl == "debug")


def test_on_minimize_changes_flag():
    page = FakePage()
    h = Handlers(page, FakeLogger(), None, None, None, None)

    h.on_minimize(None)
    assert page.window.minimized is True
