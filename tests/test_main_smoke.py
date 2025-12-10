import types
from dataclasses import dataclass

import lite_upgrade


class DummyPage:
    def __init__(self):
        self.added = None
        self.updated = 0
        self.clipboard = None
        # имитируем частые поля, если вдруг билдеры к ним полезут
        self.window = types.SimpleNamespace(minimized=False)

    def add(self, root):
        self.added = root

    def update(self):
        self.updated += 1

    def set_clipboard(self, text):
        self.clipboard = text


# примитивные контролы с нужными полями on_click
class Btn:
    def __init__(self):
        self.on_click = None


class Field:
    def __init__(self):
        # в main() привязывается on_click к suffix
        self.suffix = types.SimpleNamespace(on_click=None)
        self.value = ""
        self.visible = True
        self.disabled = False

        def _noop():
            pass

        self.update = _noop


# билдеры, которые вернут то, что ждёт main()
def fake_configure(page):
    pass


def fake_build_header():
    return object()


def fake_build_title_bar(*, t=None, on_open_history=None, on_open_info=None, on_minimize=None, on_close=None):
    # возвращаем tuple из 5 элементов, как настоящий build_title_bar
    return ("row", "info_btn", "minimize_btn", "close_btn", "drag_area")


def fake_build_inputs():
    return Field(), Field()


def fake_build_buttons():
    return "row", Btn(), Btn(), Btn()


def fake_build_footer():
    return object()


def fake_compose_page(*args, **kwargs):
    return "ROOT"


@dataclass
class UIElements:
    url_inp: str
    short_out: str
    shorten_btn: str


# Хэндлер, который просто предоставляет нужные методы
class FakeHandlers:
    def __init__(self, page, logger, state, ui: UIElements):
        self.bound = (page, logger, state, ui)

    # методы, к которым привяжутся on_click
    def on_paste(self, *_):
        pass

    def on_shorten(self, *_):
        pass

    def on_clear(self, *_):
        pass

    def on_copy(self, *_):
        pass

    def on_open_info(self, *_):
        pass

    def on_minimize(self, *_):
        pass

    def on_close(self, *_):
        pass

    # новый метод для теста истории
    def on_open_history(self, *_):
        pass


def test_main_smoke(monkeypatch):
    # подменяем то, что импортируется ВНУТРИ main()
    monkeypatch.setattr("urlcutter.ui_builders.configure_window_and_theme", fake_configure, raising=False)
    monkeypatch.setattr("urlcutter.ui_builders.build_header", fake_build_header, raising=False)
    monkeypatch.setattr("urlcutter.ui_builders.build_title_bar", fake_build_title_bar, raising=False)
    monkeypatch.setattr("urlcutter.ui_builders.build_inputs", fake_build_inputs, raising=False)
    monkeypatch.setattr("urlcutter.ui_builders.build_buttons", fake_build_buttons, raising=False)
    monkeypatch.setattr("urlcutter.ui_builders.build_footer", fake_build_footer, raising=False)
    monkeypatch.setattr("urlcutter.ui_builders.compose_page", fake_compose_page, raising=False)
    monkeypatch.setattr("urlcutter.handlers.Handlers", FakeHandlers, raising=False)

    page = DummyPage()
    lite_upgrade.main(page)

    # страница получила корневой элемент и была обновлена хотя бы раз
    assert page.added == "ROOT"
    assert page.updated >= 1
