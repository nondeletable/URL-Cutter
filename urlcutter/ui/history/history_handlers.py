# ui/history/handlers.py
from __future__ import annotations

import contextlib
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta

import flet as ft


@dataclass
class HistoryContext:
    raw_items: list[dict]
    search_ref: ft.Ref[ft.TextField]
    date_from_ref: ft.Ref[ft.TextField]
    date_to_ref: ft.Ref[ft.TextField]
    service_ref: ft.Ref[ft.Dropdown]
    render_table: callable
    set_filtered: callable
    _toast: callable
    _build_service_options: callable
    page_state: dict  # 👈 словарь с page_idx и page_size_val
    table_column_ref: ft.Ref[ft.Column]


_snack = ft.SnackBar(content=ft.Text(""), open=False)


# Экспорт в CSV
def on_export(e: ft.ControlEvent, data: list[dict], EXPORT_FIELDS: list[tuple[str, str]]):
    if not data:
        _toast(e.page, "Nothing to export")
        return

    def handle_save_result(ev: ft.FilePickerResultEvent, fp: ft.FilePicker):
        if getattr(ev, "path", None):
            try:
                with open(ev.path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f, delimiter=";")
                    w.writerow([header for _, header in EXPORT_FIELDS])
                    for it in data:
                        w.writerow([it.get(field) or "" for field, _ in EXPORT_FIELDS])
                _toast(e.page, f"Exported lines: {len(data)}")
            except Exception as ex:
                _toast(e.page, f"Export error: {ex}")

        with contextlib.suppress(Exception):
            e.page.overlay.remove(fp)
        e.page.update()

    # создаём FilePicker и передаём его в callback
    fp = ft.FilePicker(on_result=lambda ev: handle_save_result(ev, fp))
    e.page.overlay.append(fp)
    e.page.update()

    fp.save_file(
        file_name=f"history_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv",
        allowed_extensions=["csv"],
    )


def _toast(page: ft.Page, msg: str):
    _snack.content.value = msg
    _snack.open = True
    if _snack not in page.overlay:
        page.overlay.append(_snack)
    page.update()


def apply_filters(e: ft.ControlEvent | None, ctx: HistoryContext):
    # сброс ошибок на полях
    ctx.date_from_ref.current.border_color = None
    ctx.date_to_ref.current.border_color = None
    ctx.date_from_ref.current.update()
    ctx.date_to_ref.current.update()

    q = (ctx.search_ref.current.value or "").strip().lower()
    svc = ctx.service_ref.current.value or "ALL"

    def _parse_ymd(s: str | None) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.strptime(s.strip(), "%Y-%m-%d")
        except Exception:
            return None

    d_from = _parse_ymd(ctx.date_from_ref.current.value)
    d_to = _parse_ymd(ctx.date_to_ref.current.value)

    if d_from and d_to and d_from > d_to:
        ctx._toast(ctx.date_from_ref.current.page, "Incorrect dates")
        ctx.date_from_ref.current.border_color = "red"
        ctx.date_to_ref.current.border_color = "red"
        ctx.date_from_ref.current.update()
        ctx.date_to_ref.current.update()
        return

    if d_to:
        d_to = d_to + timedelta(days=1)

    def ok(it: dict) -> bool:
        if q:
            hay = " ".join(
                [
                    it.get("short_url", ""),
                    it.get("service", ""),
                    it.get("created_at_local", ""),
                ]
            ).lower()
            if q not in hay:
                return False

        if svc and svc != "ALL" and it.get("service") != svc:
            return False

        ts = it.get("created_at_local")
        dt = None
        if ts:
            try:
                dt = datetime.strptime(ts, "%Y-%m-%d %H:%M")
            except Exception:
                dt = None
        if d_from and (not dt or dt < d_from):
            return False
        return not (d_to and (not dt or dt >= d_to))

    filtered = [it for it in ctx.raw_items if ok(it)]
    ctx.set_filtered(filtered)
    ctx.render_table()


def reset_filters(e: ft.ControlEvent | None, ctx: HistoryContext):
    ctx.search_ref.current.value = ""
    ctx.date_from_ref.current.value = ""
    ctx.date_to_ref.current.value = ""
    ctx.service_ref.current.options = ctx._build_service_options()
    ctx.service_ref.current.value = "ALL"

    ctx.set_filtered(list(ctx.raw_items))

    ctx.search_ref.current.update()
    ctx.date_from_ref.current.update()
    ctx.date_to_ref.current.update()
    ctx.service_ref.current.update()
    ctx.render_table()


def on_change_page_size(e: ft.ControlEvent, ctx: HistoryContext, page_state: dict):
    try:
        page_state["page_size_val"] = int(e.control.value)
    except Exception:
        page_state["page_size_val"] = 7
    page_state["page_idx"] = 1
    ctx.render_table()


def on_prev(e: ft.ControlEvent, ctx: HistoryContext, page_state: dict):
    page_state["page_idx"] -= 1
    ctx.render_table()
    if ctx.table_column_ref.current:
        ctx.table_column_ref.current.scroll_to(offset=0, duration=100)


def on_next(e: ft.ControlEvent, ctx: HistoryContext, page_state: dict):
    page_state["page_idx"] += 1
    ctx.render_table()
    if ctx.table_column_ref.current:
        ctx.table_column_ref.current.scroll_to(offset=0, duration=100)
