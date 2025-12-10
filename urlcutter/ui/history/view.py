"""History screen (pure layout, no data/logic yet).

- Без запросов к БД и сервисам.
- Только разметка и заглушки обработчиков (print).
- I18n: принимает функцию `t(key: str) -> str`, по умолчанию возвращает ключ.
"""

from __future__ import annotations

import math
from datetime import datetime

import flet as ft

from .history_handlers import (
    HistoryContext,
    _toast,
    apply_filters,
    on_change_page_size,
    on_export,
    on_next,
    on_prev,
    reset_filters,
)


def make_history_screen(  # noqa: PLR0915
    t=lambda k: k,
    *,
    items: list[dict] | None = None,
    on_back: callable | None = None,
) -> ft.Container:
    # ---- Compact constants for narrow window ----
    HEADING_H = 36
    ROW_H = 40
    COL_SPACING = 8
    PAD = 12
    FS_BASE = 12
    FS_URL = 12
    TAB_H = 344

    label_pages_ref = ft.Ref[ft.Text]()
    btn_prev_ref = ft.Ref[ft.IconButton]()
    btn_next_ref = ft.Ref[ft.IconButton]()
    page_size_ref = ft.Ref[ft.Dropdown]()
    page_state = {"page_idx": 1, "page_size_val": 7}

    raw_items = list(items or [])
    filtered_items = list(raw_items)

    # Refs к контролам
    table_ref = ft.Ref[ft.DataTable]()
    table_column_ref = ft.Ref[ft.Column]()
    empty_hint_ref = ft.Ref[ft.Text]()

    search_ref = ft.Ref[ft.TextField]()
    date_from_ref = ft.Ref[ft.TextField]()
    date_to_ref = ft.Ref[ft.TextField]()
    service_ref = ft.Ref[ft.Dropdown]()

    btn_back = ft.IconButton(
        ft.Icons.ARROW_BACK,
        tooltip="Back",
        icon_size=24,
    )

    # ВЕШАЕМ ХЭНДЛЕР НАПРЯМУЮ, если передан
    if on_back is not None:
        btn_back.on_click = on_back
    else:
        # чтобы видеть, что клик вообще срабатывает
        btn_back.on_click = lambda e: print("[History] Back clicked (no on_back)")

    btn_export_ref = ft.Ref[ft.ElevatedButton]()

    def set_filtered(new_items: list[dict]):
        nonlocal filtered_items
        filtered_items = new_items

    def _build_service_options():
        services = sorted({it.get("service", "") for it in raw_items if it.get("service")})
        return [ft.dropdown.Option("ALL", "ALL")] + [ft.dropdown.Option(s, s) for s in services]

    def render_table():  # noqa: PLR0912
        # считаем страницы
        total = len(filtered_items)
        total_pages = max(1, math.ceil(total / ctx.page_state["page_size_val"])) if total > 0 else 1

        # приводим page_idx к допустимому диапазону
        if total == 0:
            ctx.page_state["page_idx"] = 1
        else:
            ctx.page_state["page_idx"] = max(ctx.page_state["page_idx"], 1)
            ctx.page_state["page_idx"] = min(ctx.page_state["page_idx"], total_pages)

        # слайс видимых строк
        start = 0 if total == 0 else (ctx.page_state["page_idx"] - 1) * ctx.page_state["page_size_val"]
        end = start + ctx.page_state["page_size_val"]
        visible = filtered_items[start:end] if total > 0 else []

        # таблица
        table_ref.current.rows = [make_row(it) for it in visible]
        table_ref.current.update()

        # пустое состояние
        empty_hint_ref.current.value = (
            "" if visible else ("No results. Click Reset to clear filters." if total == 0 else "No data on this page")
        )
        empty_hint_ref.current.update()

        # навигатор: "X / Y" и доступность стрелок
        if total == 0:
            label_pages_ref.current.value = "0 / 0"
            if btn_prev_ref.current:
                btn_prev_ref.current.disabled = True
            if btn_next_ref.current:
                btn_next_ref.current.disabled = True
        else:
            label_pages_ref.current.value = f"{ctx.page_state['page_idx']} / {total_pages}"
            if btn_prev_ref.current:
                btn_prev_ref.current.disabled = ctx.page_state["page_idx"] <= 1
            if btn_next_ref.current:
                btn_next_ref.current.disabled = ctx.page_state["page_idx"] >= total_pages

        label_pages_ref.current.update()
        if btn_prev_ref.current:
            btn_prev_ref.current.update()
        if btn_next_ref.current:
            btn_next_ref.current.update()

        if btn_export_ref.current:
            btn_export_ref.current.tooltip = f"Export {total} rows"
            btn_export_ref.current.update()

    EXPORT_FIELDS = [
        ("created_at_local", "Date"),
        ("service", "Service"),
        ("short_url", "Short URL"),
        ("long_url", "Long URL"),  # 👈 поле есть в CSV, но не в таблице
    ]

    ctx = HistoryContext(
        raw_items=raw_items,
        search_ref=search_ref,
        date_from_ref=date_from_ref,
        date_to_ref=date_to_ref,
        service_ref=service_ref,
        render_table=render_table,
        set_filtered=set_filtered,
        _toast=_toast,
        _build_service_options=_build_service_options,
        page_state=page_state,
        table_column_ref=table_column_ref,
    )

    def build_filters():
        search = ft.TextField(
            label="Search",
            content_padding=ft.padding.only(left=PAD, right=PAD, top=17, bottom=17),
            dense=True,
            expand=True,
            ref=search_ref,
            on_submit=lambda e: apply_filters(e, ctx),
        )
        date_from = ft.TextField(
            label="Date from",
            dense=True,
            width=120,
            content_padding=ft.padding.only(left=PAD, right=PAD, top=17, bottom=17),
            ref=date_from_ref,
            on_submit=lambda e: apply_filters(e, ctx),
        )
        date_to = ft.TextField(
            label="Date to",
            dense=True,
            width=120,
            content_padding=ft.padding.only(left=PAD, right=PAD, top=17, bottom=17),
            ref=date_to_ref,
            on_submit=lambda e: apply_filters(e, ctx),
        )

        service = ft.Dropdown(
            label="Service",
            dense=True,
            width=140,
            options=_build_service_options(),
            value="ALL",
            ref=service_ref,
        )

        btn_apply = ft.ElevatedButton("Apply", height=42, width=80, on_click=lambda e: apply_filters(e, ctx))
        btn_reset = ft.ElevatedButton("Reset", height=42, width=80, on_click=lambda e: reset_filters(e, ctx))
        btn_export = ft.ElevatedButton(
            "Export CSV",
            ref=btn_export_ref,
            on_click=lambda e: on_export(e, filtered_items, EXPORT_FIELDS),
            tooltip="Export current selection",
            color=ft.Colors.WHITE,
            bgcolor="#EB244E",
            height=42,
            width=110,
        )

        return ft.ResponsiveRow(
            controls=[
                ft.Container(search, col={"xs": 12, "md": 6}),
                ft.Container(date_from, col={"xs": 6, "md": 3}),
                ft.Container(date_to, col={"xs": 6, "md": 3}),
                ft.Container(service, col={"xs": 12, "md": 4}),
                ft.Container(
                    ft.Row([btn_apply, btn_reset, btn_export], spacing=COL_SPACING, wrap=False),
                    col=12,
                    padding=ft.padding.only(top=4),
                ),
            ],
            spacing=COL_SPACING,
            run_spacing=COL_SPACING,
        )

    # ---- Table rows (compact, English headers) ----
    def _txt(v: str, size=FS_BASE):
        return ft.Text(v, size=size)

    def _url_cell(v: str):
        return ft.Text(
            v or "—",
            size=FS_URL,
            font_family="monospace",
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
            tooltip=v or "",
            selectable=True,
        )

    def _copy(e, s: str):  # quick copy helper
        p = e.control.page
        p.set_clipboard(s)
        p.snack_bar = ft.SnackBar(ft.Text("Copied"), open=True)
        p.update()

    def _open(e, url: str):
        e.control.page.launch_url(url)

    def make_row(it) -> ft.DataRow:
        created_at = (
            getattr(it, "created_at_local", None) or getattr(it, "created_at_utc", None)
            if not isinstance(it, dict)
            else it.get("created_at_local", "—")
        )

        service = getattr(it, "service", None) if not isinstance(it, dict) else it.get("service", "—")
        short_url = getattr(it, "short_url", None) if not isinstance(it, dict) else it.get("short_url", "")

        # форматируем дату, только если она datetime
        if isinstance(created_at, datetime):
            created_at = created_at.strftime("%Y-%m-%d %H:%M")

        return ft.DataRow(
            cells=[
                ft.DataCell(_txt(created_at or "—")),  # Date
                ft.DataCell(_txt(str(service or "—"))),  # Service
                ft.DataCell(_url_cell(short_url or "")),  # Short URL
                ft.DataCell(
                    ft.Row(
                        [
                            ft.IconButton(
                                ft.Icons.CONTENT_COPY,
                                tooltip="Copy",
                                icon_size=16,
                                on_click=lambda e, s=short_url: _copy(e, s),
                            ),
                            ft.IconButton(
                                ft.Icons.OPEN_IN_NEW,
                                tooltip="Open",
                                icon_size=16,
                                on_click=lambda e, u=short_url: _open(e, u),
                            ),
                        ],
                        spacing=2,
                    )
                ),
            ]
        )

    # Первичная выборка для UI до первых update()
    initial_total = len(filtered_items)
    initial_total_pages = max(1, math.ceil(initial_total / ctx.page_state["page_size_val"])) if initial_total > 0 else 1

    # какие строки видны на старте
    _initial_start = 0 if initial_total == 0 else (ctx.page_state["page_idx"] - 1) * ctx.page_state["page_size_val"]
    _initial_end = _initial_start + ctx.page_state["page_size_val"]
    initial_visible = filtered_items[_initial_start:_initial_end] if initial_total > 0 else []

    # что положить в таблицу и хинт
    initial_rows = [make_row(it) for it in initial_visible]
    initial_empty_text = (
        ""
        if initial_rows
        else ("No results. Click Reset to clear filters." if initial_total == 0 else "No data on this page")
    )

    # подпись страниц и состояние стрелок
    initial_pages_label = "0 / 0" if initial_total == 0 else f"{ctx.page_state['page_idx']} / {initial_total_pages}"
    initial_prev_disabled = ctx.page_state["page_idx"] <= 1
    initial_next_disabled = initial_total_pages <= 1

    def build_table():
        # таблица
        table = ft.DataTable(
            ref=table_ref,
            columns=[
                ft.DataColumn(_txt("Date")),
                ft.DataColumn(_txt("Service")),
                ft.DataColumn(_txt("Short URL")),
                ft.DataColumn(ft.Text("")),
            ],
            rows=initial_rows,
            column_spacing=COL_SPACING,
            heading_row_height=HEADING_H,
            data_row_max_height=ROW_H,
            horizontal_margin=0,
        )

        empty_hint = ft.Text(initial_empty_text, ref=empty_hint_ref)

        # Обертка для таблицы с прокруткой
        table_scroll = ft.Container(
            content=ft.Column(
                [table, empty_hint],
                spacing=COL_SPACING,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
                ref=table_column_ref,
            ),
            height=TAB_H,
        )
        return table_scroll

    def build_pagination():
        page_size = ft.Dropdown(
            width=88,
            value=str(ctx.page_state["page_size_val"]),
            options=[ft.dropdown.Option(str(x)) for x in (7, 10, 20, 50)],
            on_change=lambda e: on_change_page_size(e, ctx, ctx.page_state),
            ref=page_size_ref,
        )

        pagination = ft.Row(
            controls=[
                ft.Text("Rows/page:"),
                page_size,
                ft.Container(expand=True),
                ft.Text(initial_pages_label, ref=label_pages_ref),
                ft.IconButton(
                    ft.Icons.CHEVRON_LEFT,
                    tooltip="Prev",
                    icon_size=18,
                    ref=btn_prev_ref,
                    on_click=lambda e: on_prev(e, ctx, ctx.page_state),
                    disabled=initial_prev_disabled,
                ),
                ft.IconButton(
                    ft.Icons.CHEVRON_RIGHT,
                    tooltip="Next",
                    icon_size=18,
                    ref=btn_next_ref,
                    on_click=lambda e: on_next(e, ctx, ctx.page_state),
                    disabled=initial_next_disabled,
                ),
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return pagination

    filters_row = build_filters()
    table_scroll = build_table()
    pagination = build_pagination()

    # 3) Основной контент прижат к верху окна:
    main_content = ft.Column(
        controls=[
            filters_row,
            table_scroll,  # ← наша прокручиваемая середина
            # убери нижний Divider, он визуально отталкивает пагинацию
        ],
        spacing=COL_SPACING,
        expand=True,
        alignment=ft.MainAxisAlignment.START,  # ← прижать вверх
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,  # ← тянуть по ширине
    )

    # 4) Низ: пагинация прижата к низу
    layout = ft.Column(
        controls=[
            main_content,  # ← растягивается
            pagination,  # ← всегда внизу
        ],
        spacing=0,
        expand=True,
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,  # ← первый элемент к верху, второй к низу
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    # 5) Корневой контейнер — тянем на весь экран, но НЕ центрируем контент:
    return ft.Container(
        layout,
        padding=ft.padding.only(left=PAD, right=PAD, top=COL_SPACING, bottom=PAD),
        expand=True,
        # alignment не задаём, чтобы не центрировать дочерний Column
    )
