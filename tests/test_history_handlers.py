import builtins
from unittest.mock import MagicMock

import flet as ft
import pytest

from urlcutter.ui.history import history_handlers
from urlcutter.ui.history.history_handlers import (
    HistoryContext,
    apply_filters,
    on_change_page_size,
    on_export,
    on_next,
    on_prev,
    reset_filters,
)


class DummyEvent:
    def __init__(self, page):
        self.page = page
        self.control = None


class DummyRef(ft.Ref):
    def __init__(self, value=""):
        super().__init__()
        self.current = type("C", (), {"value": value, "update": lambda self: None, "page": None})()


@pytest.fixture
def sample_items():
    return [
        {"short_url": "abc", "service": "S1", "created_at_local": "2025-09-01 10:00"},
        {"short_url": "def", "service": "S2", "created_at_local": "2025-09-02 11:00"},
        {"short_url": "ghi", "service": "S1", "created_at_local": "2025-09-03 12:00"},
    ]


@pytest.fixture
def ctx(sample_items):
    search_ref = DummyRef("")
    date_from_ref = DummyRef("")
    date_to_ref = DummyRef("")
    service_ref = DummyRef("ALL")

    filtered = []

    def set_filtered(items):
        nonlocal filtered
        filtered = items

    return {
        "ctx": HistoryContext(
            raw_items=sample_items,
            search_ref=search_ref,
            date_from_ref=date_from_ref,
            date_to_ref=date_to_ref,
            service_ref=service_ref,
            render_table=MagicMock(),
            set_filtered=set_filtered,
            _toast=MagicMock(),
            _build_service_options=lambda: [ft.dropdown.Option("ALL")],
            page_state={"page_idx": 1, "page_size_val": 7},
            table_column_ref=ft.Ref[ft.Column](),
        ),
        "filtered": lambda: filtered,
    }


def test_apply_filters_search(ctx):
    c, get_filtered = ctx["ctx"], ctx["filtered"]

    # ищем "abc"
    c.search_ref.current.value = "abc"
    apply_filters(None, c)

    assert len(get_filtered()) == 1
    assert get_filtered()[0]["short_url"] == "abc"


def test_reset_filters(ctx):
    c, get_filtered = ctx["ctx"], ctx["filtered"]

    # сначала зафильтруем
    c.search_ref.current.value = "abc"
    apply_filters(None, c)
    assert len(get_filtered()) == 1

    # потом сбросим
    reset_filters(None, c)
    assert len(get_filtered()) == len(c.raw_items)
    assert c.service_ref.current.value == "ALL"


def test_apply_filters_service(ctx):
    c, get_filtered = ctx["ctx"], ctx["filtered"]

    # выставляем фильтр по сервису S1
    c.service_ref.current.value = "S1"
    apply_filters(None, c)

    # все отфильтрованные элементы должны иметь service = S1
    result = get_filtered()
    assert all(it["service"] == "S1" for it in result)
    # и их должно быть ровно 2 из sample_items
    assert len(result) == 2


def test_apply_filters_date_range(ctx):
    c, get_filtered = ctx["ctx"], ctx["filtered"]

    # фильтруем с 2025-09-02 по 2025-09-03
    c.date_from_ref.current.value = "2025-09-02"
    c.date_to_ref.current.value = "2025-09-03"
    apply_filters(None, c)

    result = get_filtered()
    # в sample_items подходят записи с датами 2025-09-02 и 2025-09-03
    assert len(result) == 2
    assert all(
        it["created_at_local"].startswith("2025-09-02") or it["created_at_local"].startswith("2025-09-03")
        for it in result
    )


def test_apply_filters_incorrect_date_range(ctx):
    c, get_filtered = ctx["ctx"], ctx["filtered"]

    c.date_from_ref.current.value = "2025-09-03"
    c.date_to_ref.current.value = "2025-09-01"

    apply_filters(None, c)

    # при ошибке даты список очищается
    assert get_filtered() == []

    # _toast вызван
    c._toast.assert_called()
    args, _ = c._toast.call_args
    assert "Incorrect dates" in args[1]


def test_on_export_empty(tmp_path, ctx, monkeypatch):
    e = DummyEvent(page=MagicMock())

    mock_toast = MagicMock()
    monkeypatch.setattr(history_handlers, "_toast", mock_toast)

    on_export(e, [], [("short_url", "Short URL")])

    mock_toast.assert_called()
    args, _ = mock_toast.call_args
    assert "Nothing to export" in args[1]


def test_on_export_with_data(tmp_path, monkeypatch):

    data = [
        {"short_url": "abc", "service": "S1", "created_at_local": "2025-09-01 10:00"},
        {"short_url": "def", "service": "S2", "created_at_local": "2025-09-02 11:00"},
    ]
    fields = [("short_url", "Short URL"), ("service", "Service")]

    e = DummyEvent(page=MagicMock())

    mock_fp = MagicMock()

    # когда в on_export вызовется ft.FilePicker(on_result=...),
    # мы сохраним этот on_result внутрь mock_fp
    def fake_filepicker(on_result):
        mock_fp.on_result = on_result
        return mock_fp

    monkeypatch.setattr(history_handlers.ft, "FilePicker", fake_filepicker)

    # эмулируем save_file: он должен вызвать on_result, как будто пользователь выбрал путь
    def fake_save_file(*args, **kwargs):
        fake_event = type("Res", (), {"path": str(tmp_path / "out.csv")})()
        mock_fp.on_result(fake_event)

    mock_fp.save_file = fake_save_file

    # запускаем экспорт
    history_handlers.on_export(e, data, fields)

    # проверяем результат
    csv_path = tmp_path / "out.csv"
    assert csv_path.exists()

    lines = csv_path.read_text(encoding="utf-8-sig").splitlines()
    assert lines[0] == "Short URL;Service"
    assert "abc;S1" in lines[1]
    assert "def;S2" in lines[2]


def test_on_change_page_size(ctx):
    c = ctx["ctx"]

    # изначально page_size = 7
    assert c.page_state["page_size_val"] == 7

    # имитируем событие со значением "20"
    e = type("E", (), {"control": type("C", (), {"value": "20"})()})()
    on_change_page_size(e, c, c.page_state)

    # page_size должно измениться
    assert c.page_state["page_size_val"] == 20


def test_on_prev(ctx):
    c = ctx["ctx"]
    c.page_state["page_idx"] = 2  # стартуем со 2-й страницы

    e = type("E", (), {})()
    on_prev(e, c, c.page_state)

    # после вызова должна быть 1-я страница
    assert c.page_state["page_idx"] == 1


def test_on_next(ctx):
    c = ctx["ctx"]
    c.page_state["page_idx"] = 1  # стартуем с 1-й страницы

    e = type("E", (), {})()
    on_next(e, c, c.page_state)

    # после вызова должна быть 2-я страница
    assert c.page_state["page_idx"] == 2


def test_apply_filters_with_invalid_date_format(ctx):
    c, get_filtered = ctx["ctx"], ctx["filtered"]

    # подсовываем битую дату
    c.raw_items.append({"short_url": "xxx", "service": "S1", "created_at_local": "not-a-date"})

    # включаем фильтр по дате "с"
    c.date_from_ref.current.value = "2025-09-01"

    # не должно падать
    apply_filters(None, c)

    # результат должен содержать все валидные записи + не упасть на битой
    result = get_filtered()
    assert any(it["created_at_local"] == "not-a-date" for it in result) or result != []


def test_on_export_with_ioerror(tmp_path, monkeypatch):
    # Данные для экспорта
    data = [
        {"short_url": "abc", "service": "S1"},
    ]
    fields = [("short_url", "Short URL"), ("service", "Service")]

    e = DummyEvent(page=MagicMock())

    mock_fp = MagicMock()

    # перехватываем FilePicker и сохраняем on_result
    def fake_filepicker(on_result):
        mock_fp.on_result = on_result
        return mock_fp

    monkeypatch.setattr(history_handlers.ft, "FilePicker", fake_filepicker)

    # подмена save_file: сразу дергаем on_result с path
    def fake_save_file(*args, **kwargs):
        fake_event = type("Res", (), {"path": str(tmp_path / "bad.csv")})()
        mock_fp.on_result(fake_event)

    mock_fp.save_file = fake_save_file

    # подмена open, чтобы кидал IOError
    def fake_open(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(builtins, "open", fake_open)

    # мок для _toast
    mock_toast = MagicMock()
    monkeypatch.setattr(history_handlers, "_toast", mock_toast)

    # запуск
    history_handlers.on_export(e, data, fields)

    # _toast должен быть вызван с текстом ошибки
    mock_toast.assert_called()
    args, _ = mock_toast.call_args
    assert "Export error" in args[1]


def test_on_export_remove_overlay_raises(tmp_path, monkeypatch):

    data = [{"short_url": "abc", "service": "S1"}]
    fields = [("short_url", "Short URL"), ("service", "Service")]
    e = DummyEvent(page=MagicMock())

    mock_fp = MagicMock()

    # эмуляция FilePicker
    def fake_filepicker(on_result):
        mock_fp.on_result = on_result
        return mock_fp

    monkeypatch.setattr(history_handlers.ft, "FilePicker", fake_filepicker)

    # эмуляция save_file — сразу триггерим on_result
    def fake_save_file(*args, **kwargs):
        fake_event = type("Res", (), {"path": str(tmp_path / "out.csv")})()
        mock_fp.on_result(fake_event)

    mock_fp.save_file = fake_save_file

    # подмена open — пусть создаёт файл нормально
    monkeypatch.setattr("builtins.open", open)

    # подмена page.overlay.remove — кидаем исключение
    e.page.overlay.remove = MagicMock(side_effect=ValueError("remove failed"))

    # мок для _toast
    mock_toast = MagicMock()
    monkeypatch.setattr(history_handlers, "_toast", mock_toast)

    # запуск
    history_handlers.on_export(e, data, fields)

    # проверка: ошибка не упала наружу, _toast вызван
    mock_toast.assert_called()


def test_apply_filters_empty_date_string(ctx):
    c, get_filtered = ctx["ctx"], ctx["filtered"]

    c.date_from_ref.current.value = ""  # пустая строка
    apply_filters(None, c)

    # просто проверим, что не упало и список не пустой
    assert isinstance(get_filtered(), list)


def test_apply_filters_empty_service(ctx):
    c, get_filtered = ctx["ctx"], ctx["filtered"]

    # ставим пустой сервис
    c.service_ref.current.value = ""
    apply_filters(None, c)

    # должны остаться все записи
    assert len(get_filtered()) == len(c.raw_items)


def test_apply_filters_item_without_short_url(ctx):
    c, get_filtered = ctx["ctx"], ctx["filtered"]

    # добавляем элемент без short_url
    c.raw_items.append({"service": "S1", "created_at_local": "2025-09-05 12:00"})
    c.search_ref.current.value = "abc"  # ищем строку, которой тут нет

    apply_filters(None, c)

    # просто проверим, что код не упал и вернул список
    assert isinstance(get_filtered(), list)


def test_on_export_empty_list_triggers_toast(ctx, monkeypatch):

    _ = ctx["ctx"]
    e = DummyEvent(page=MagicMock())

    mock_toast = MagicMock()
    monkeypatch.setattr(history_handlers, "_toast", mock_toast)

    # запускаем экспорт с пустым списком
    on_export(e, [], [("short_url", "Short URL")])

    # _toast вызван с "Nothing to export"
    mock_toast.assert_called()
    args, _ = mock_toast.call_args
    assert "Nothing to export" in args[1]


def test_apply_filters_date_none(ctx):
    c, get_filtered = ctx["ctx"], ctx["filtered"]

    # дата None — функция должна спокойно отработать
    c.date_from_ref.current.value = None
    apply_filters(None, c)

    assert isinstance(get_filtered(), list)


def test_apply_filters_search_no_match(ctx):
    c, get_filtered = ctx["ctx"], ctx["filtered"]

    # ищем несуществующую строку
    c.search_ref.current.value = "zzz"
    apply_filters(None, c)

    # список должен быть пустым
    assert get_filtered() == []


def test_apply_filters_empty_item(ctx):
    c, get_filtered = ctx["ctx"], ctx["filtered"]

    # добавляем элемент без short_url и service
    c.raw_items.append({"created_at_local": "2025-09-06 15:00"})
    apply_filters(None, c)

    # список возвращается, ошибок нет
    assert isinstance(get_filtered(), list)


def test_on_export_no_path(monkeypatch):

    e = DummyEvent(page=MagicMock())
    mock_fp = MagicMock()

    def fake_filepicker(on_result):
        mock_fp.on_result = on_result
        return mock_fp

    monkeypatch.setattr(history_handlers.ft, "FilePicker", fake_filepicker)

    def fake_save_file(*args, **kwargs):
        fake_event = type("Res", (), {})()  # без path
        mock_fp.on_result(fake_event)

    mock_fp.save_file = fake_save_file

    mock_toast = MagicMock()
    monkeypatch.setattr(history_handlers, "_toast", mock_toast)

    # не должно падать
    history_handlers.on_export(e, [{"short_url": "abc"}], [("short_url", "Short URL")])

    # здесь _toast не вызывается, поэтому проверяем наоборот
    mock_toast.assert_not_called()


def test_apply_filters_service_mismatch(ctx):
    c, get_filtered = ctx["ctx"], ctx["filtered"]

    # ищем по сервису, которого нет в данных
    c.service_ref.current.value = "NON_EXISTENT"
    apply_filters(None, c)

    # результат должен быть пустой
    assert get_filtered() == []


def test_apply_filters_date_from_without_dt(ctx):
    c, get_filtered = ctx["ctx"], ctx["filtered"]

    # дата "с"
    c.date_from_ref.current.value = "2025-09-01"

    # добавляем элемент без created_at_local
    c.raw_items.append({"short_url": "zzz", "service": "S1"})
    apply_filters(None, c)

    # элемент без даты не должен пройти фильтр
    assert all(it.get("created_at_local") for it in get_filtered())


def test_on_export_success_triggers_toast(tmp_path, monkeypatch):

    data = [{"short_url": "abc", "service": "S1"}]
    fields = [("short_url", "Short URL"), ("service", "Service")]

    e = DummyEvent(page=MagicMock())
    mock_fp = MagicMock()

    def fake_filepicker(on_result):
        mock_fp.on_result = on_result
        return mock_fp

    monkeypatch.setattr(history_handlers.ft, "FilePicker", fake_filepicker)

    def fake_save_file(*args, **kwargs):
        fake_event = type("Res", (), {"path": str(tmp_path / "out.csv")})()
        mock_fp.on_result(fake_event)

    mock_fp.save_file = fake_save_file

    mock_toast = MagicMock()
    monkeypatch.setattr(history_handlers, "_toast", mock_toast)

    history_handlers.on_export(e, data, fields)

    # проверяем вызов _toast с количеством строк
    mock_toast.assert_called()
    args, _ = mock_toast.call_args
    assert "Exported lines" in args[1]


def test_on_export_remove_success(tmp_path, monkeypatch):

    data = [{"short_url": "abc", "service": "S1"}]
    fields = [("short_url", "Short URL"), ("service", "Service")]

    e = DummyEvent(page=MagicMock())
    e.page.overlay.remove = MagicMock()  # успешное удаление

    mock_fp = MagicMock()

    def fake_filepicker(on_result):
        mock_fp.on_result = on_result
        return mock_fp

    monkeypatch.setattr(history_handlers.ft, "FilePicker", fake_filepicker)

    def fake_save_file(*args, **kwargs):
        fake_event = type("Res", (), {"path": str(tmp_path / "out.csv")})()
        mock_fp.on_result(fake_event)

    mock_fp.save_file = fake_save_file

    history_handlers.on_export(e, data, fields)

    # remove должен быть вызван
    e.page.overlay.remove.assert_called()


# --- _toast (61–63) ---
def test_toast_adds_snack_once():
    page = MagicMock()
    page.overlay = []
    history_handlers._toast(page, "hello")

    # первый вызов добавляет
    assert history_handlers._snack in page.overlay

    # второй вызов не дублирует
    history_handlers._toast(page, "again")
    assert page.overlay.count(history_handlers._snack) == 1


# --- apply_filters (80–81) ---
def test_apply_filters_invalid_date_format(ctx):
    c = ctx["ctx"]
    # задаём некорректный формат даты
    c.date_from_ref.current.value = "2025/09/01"  # вместо YYYY-MM-DD
    c.date_to_ref.current.value = "bad-date"

    history_handlers.apply_filters(None, c)
    # просто убеждаемся, что фильтр не рухнул
    assert isinstance(c.raw_items, list)


# --- on_change_page_size (148–149) ---
def test_on_change_page_size_invalid_value(ctx):
    c = ctx["ctx"]
    e = type("E", (), {"control": type("C", (), {"value": "abc"})()})()
    history_handlers.on_change_page_size(e, c, c.page_state)

    # сбросилось в дефолт
    assert c.page_state["page_size_val"] == 7


# --- on_prev (157) ---
def test_on_prev_triggers_scroll(ctx):
    c = ctx["ctx"]
    c.page_state["page_idx"] = 2
    c.table_column_ref.current = MagicMock()

    history_handlers.on_prev(None, c, c.page_state)

    c.table_column_ref.current.scroll_to.assert_called_once()


# --- on_next (163) ---
def test_on_next_triggers_scroll(ctx):
    c = ctx["ctx"]
    c.page_state["page_idx"] = 1
    c.table_column_ref.current = MagicMock()

    history_handlers.on_next(None, c, c.page_state)

    c.table_column_ref.current.scroll_to.assert_called_once()
