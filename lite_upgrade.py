# 1) Imports
from __future__ import annotations

import inspect
import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _TimeoutError
from types import SimpleNamespace

import pyshorteners

import urlcutter.patches.fix_alembic_version  # noqa: F401
from urlcutter import shorten_via_tinyurl_core as _shorten_core
from urlcutter.logging_utils import setup_logging
from urlcutter.normalization import _url_fingerprint, normalize_url
from urlcutter.protection import (
    CB_COOLDOWN_SEC,
    CB_FAIL_THRESHOLD,
    CIRCUIT_COOLDOWN_SEC,
    CIRCUIT_FAIL_THRESHOLD,
    CLIENT_RPM_LIMIT,
    RATE_LIMIT_WINDOW_SEC,
    AppState,
    _get_state,
    _reset_state,
    circuit_blocked,
    cooldown_left,
    rate_limit_allow,
    record_failure,
    record_success,
)
from urlcutter.protection import internet_ok as _internet_ok_core

# Публичные атрибуты для тестов:
FutTimeout = _TimeoutError


__all__ = [
    "normalize_url",
    "_url_fingerprint",
    "setup_logging",
    "shorten_via_tinyurl",
    "AppState",
    "_get_state",
    "_reset_state",
    "circuit_blocked",
    "cooldown_left",
    "rate_limit_allow",
    "record_failure",
    "record_success",
    "CB_COOLDOWN_SEC",
    "CB_FAIL_THRESHOLD",
    "CIRCUIT_COOLDOWN_SEC",
    "CIRCUIT_FAIL_THRESHOLD",
    "CLIENT_RPM_LIMIT",
    "RATE_LIMIT_WINDOW_SEC",
    "internet_ok",
]


# 2) Константы / Конфигурация
REQUEST_TIMEOUT = 8.0
RETRIES = 1

# ---- Ограничения и защита от капов удалённых сервисов ----
CONNECTIVITY_PROBE_URL = "https://www.google.com/generate_204"
CONNECTIVITY_TIMEOUT = 2.0  # короткий таймаут для проверки сети

# ---- Логирование ----
LOG_ENABLED = True
LOG_DEBUG = os.getenv("URLCUTTER_DEBUG") == "1"
LOG_FILE = "logs/app.log"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUPS = 3


# публичная функция, которую дергают тесты
def internet_ok(logger):
    return _internet_ok_core(logger, AppState_cls=AppState)


def shorten_via_tinyurl(
    url: str,
    timeout: float | None = None,
    *,
    _get=None,
    _shortener_factory=None,
    _pool_factory=None,
) -> str:
    shortener_factory = _shortener_factory or pyshorteners.Shortener
    pool_factory = _pool_factory or ThreadPoolExecutor
    return _shorten_core(
        url,
        timeout,
        _get=_get,
        _shortener_factory=shortener_factory,
        _pool_factory=pool_factory,
    )


# 8) Точка входа (инициализация и «провода»)
def main(page):  # можно без аннотации, чтобы не держать Flet на импорте
    # локальные импорты — так тестовый monkeypatch перехватывает их корректно
    import flet as ft  # NEW: нужен для Container

    import urlcutter.ui_builders as U  # noqa: PLC0415
    from urlcutter.db.migrate import upgrade_to_head  # noqa: PLC0415
    from urlcutter.handlers import Handlers  # noqa: PLC0415

    upgrade_to_head()

    logger = setup_logging(enabled=LOG_ENABLED, debug=LOG_DEBUG)
    U.configure_window_and_theme(page)

    # --- строим основной UI шортенера (как раньше) ---
    header_col = U.build_header()
    url_input_field, short_url_field = U.build_inputs()
    button_row, shorten_button, clear_button, copy_button = U.build_buttons()
    footer_container = U.build_footer()

    # --- центральная область, куда подставляется контент (шортенер ИЛИ история) ---
    main_body = ft.Container(expand=True)

    # --- ui-алиасы и состояние (как у тебя было) ---
    ui = SimpleNamespace(
        url_input_field=url_input_field,
        url_inp=url_input_field,
        short_url_field=short_url_field,
        short_out=short_url_field,
        shorten_button=shorten_button,
        shorten_btn=shorten_button,
    )
    state = AppState()

    params = {
        "page": page,
        "logger": logger,
        "state": state,
        # имена на все случаи: боевой Handlers и тестовый FakeHandlers
        "url_input_field": url_input_field,
        "url_inp": url_input_field,
        "short_url_field": short_url_field,
        "short_out": short_url_field,
        "shorten_button": shorten_button,
        "shorten_btn": shorten_button,
        "ui": ui,
    }

    # --- создаём handlers ДО title_bar, чтобы сразу передать его методы в меню ---
    try:
        sig = inspect.signature(Handlers.__init__)
    except (TypeError, ValueError):
        sig = inspect.signature(Handlers)
    kwargs = {name: params[name] for name in sig.parameters if name != "self" and name in params}
    handlers = Handlers(**kwargs)

    # даём обработчику доступ к центральной области для показа «Истории»
    if hasattr(handlers, "attach_main_body"):
        handlers.attach_main_body(main_body)

    # 1) собираем title bar (ТЕПЕРЬ 5 значений)
    title_row, info_btn, minimize_btn, close_btn, drag_area = U.build_title_bar(
        t=lambda k: k,
        on_open_history=handlers.on_open_history,
        on_open_info=handlers.on_open_info,
        on_minimize=handlers.on_minimize,
        on_close=handlers.on_close,
    )

    # 2) собираем стартовый экран
    root = U.compose_page(
        title_bar=title_row,
        header_col=header_col,
        url_input_field=url_input_field,
        short_url_field=short_url_field,
        button_row=button_row,
        footer_container=footer_container,
        main_body=main_body,
    )
    page.add(root)

    # 3) сохраним ссылки в handlers, чтобы переключать бар в on_open_history/_back_to_saved_view
    handlers.title_row = title_row
    handlers.info_btn = info_btn
    handlers.minimize_btn = minimize_btn
    handlers.close_btn = close_btn
    handlers.drag_area = drag_area

    # 4) бинды кнопок как у тебя
    url_input_field.suffix.on_click = handlers.on_paste
    shorten_button.on_click = handlers.on_shorten
    clear_button.on_click = handlers.on_clear
    copy_button.on_click = handlers.on_copy

    page.update()


if __name__ == "__main__":  # pragma: no cover
    import multiprocessing as mp

    mp.freeze_support()
    import flet as ft

    ft.app(target=main, view=ft.AppView.FLET_APP)
