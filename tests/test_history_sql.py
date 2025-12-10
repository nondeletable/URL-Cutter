import csv
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import SQLAlchemyError

from urlcutter.db.repo.errors import NotFoundError, StorageError, ValidationError
from urlcutter.db.repo.history_sql import SqlAlchemyHistoryService, _utc_boundaries_from_local_dates
from urlcutter.db.repo.schemas import ExportSpec, HistoryFilters, LinkRecord, PageSpec, SortSpec


def test_add_and_list_roundtrip(db_session):
    svc = SqlAlchemyHistoryService()

    # 1. добавляем запись
    rec = LinkRecord(
        id=None,
        long_url="https://example.com",
        short_url="abc",
        service="S1",
        created_at_utc=None,
    )
    stored = svc.add(rec)

    assert stored.id is not None
    assert stored.service == "S1"

    # 2. получаем список (без фильтров, сортировка по created_at)
    page = svc.list(
        filters=HistoryFilters(),
        sort=SortSpec(),
        page=PageSpec(page=1, page_size=10),
    )

    assert page.total >= 1
    assert any(item.short_url == "abc" for item in page.items)


def test_distinct_services(db_session):
    svc = SqlAlchemyHistoryService()

    # добавляем несколько записей с разными сервисами
    svc.add(LinkRecord(id=None, long_url="https://a.com", short_url="a", service="S1", created_at_utc=None))
    svc.add(LinkRecord(id=None, long_url="https://b.com", short_url="b", service="S2", created_at_utc=None))
    svc.add(LinkRecord(id=None, long_url="https://c.com", short_url="c", service="S1", created_at_utc=None))

    # получаем список уникальных сервисов
    services = svc.distinct_services()

    assert isinstance(services, list)
    # проверяем, что наши сервисы точно есть среди всех
    assert {"S1", "S2"}.issubset(set(services))


def test_add_and_retrieve_from_db(db_session):

    svc = SqlAlchemyHistoryService()

    # добавляем запись
    rec = LinkRecord(
        id=None,
        long_url="https://example.com",
        short_url="xyz987",
        service="SVCX",
        created_at_utc=None,
    )
    stored = svc.add(rec)

    # проверяем, что id и created_at_utc назначились
    assert stored.id is not None
    assert stored.created_at_utc is not None

    # достаём обратно через list
    page = svc.list(
        filters=HistoryFilters(),
        sort=SortSpec(),
        page=PageSpec(page=1, page_size=10),
    )

    # в items должны быть записи, и одна из них — наша
    items = [it.short_url for it in page.items]
    assert "xyz987" in items


def test_delete_record(db_session):
    svc = SqlAlchemyHistoryService()

    # создаём запись
    rec = LinkRecord(
        id=None,
        long_url="https://todelete.com",
        short_url="del1",
        service="DEL",
        created_at_utc=datetime.now(UTC),
        copy_count=0,
    )
    stored = svc.add(rec)

    # 1. удаляем запись
    assert svc.delete(stored.id) is True

    # 2. убеждаемся, что записи больше нет
    page_after = svc.list(
        filters=HistoryFilters(),
        sort=SortSpec(),
        page=PageSpec(page=1, page_size=10),
    )
    record_after = next((item for item in page_after.items if item.short_url == "del1"), None)
    assert record_after is None

    # 3. повторное удаление возвращает False
    assert svc.delete(stored.id) is False


def test_increment_copy_count(db_session):
    svc = SqlAlchemyHistoryService()

    rec = LinkRecord(
        id=None,
        long_url="https://counter.com",
        short_url="cnt1",
        service="CNT",
        created_at_utc=datetime.now(UTC),
        copy_count=0,
    )
    stored = svc.add(rec)

    # Проверяем начальное значение copy_count
    page_before = svc.list(
        filters=HistoryFilters(),
        sort=SortSpec(),
        page=PageSpec(page=1, page_size=10),
    )
    record_before = next((item for item in page_before.items if item.short_url == "cnt1"), None)
    assert record_before is not None
    assert record_before.copy_count == 0

    # Вызываем метод increment_copy_count
    svc.increment_copy_count(stored.id)

    # Проверяем, что copy_count увеличился
    page_after = svc.list(
        filters=HistoryFilters(),
        sort=SortSpec(),
        page=PageSpec(page=1, page_size=10),
    )
    record_after = next((item for item in page_after.items if item.short_url == "cnt1"), None)
    assert record_after is not None
    assert record_after.copy_count == 1


def test_list_invalid_page_and_size(db_session):
    svc = SqlAlchemyHistoryService()

    # page < 1
    with pytest.raises(ValidationError):
        svc.list(
            filters=HistoryFilters(),
            sort=SortSpec(),
            page=PageSpec(page=0, page_size=10),
        )

    # page_size <= 0
    with pytest.raises(ValidationError):
        svc.list(
            filters=HistoryFilters(),
            sort=SortSpec(),
            page=PageSpec(page=1, page_size=0),
        )


def test_list_invalid_sort_field(db_session):
    svc = SqlAlchemyHistoryService()

    with pytest.raises(ValidationError):
        svc.list(
            filters=HistoryFilters(),
            sort=SortSpec(field="not_a_field"),  # type: ignore[arg-type]
            page=PageSpec(page=1, page_size=10),
        )


@pytest.mark.parametrize(
    "bad_record",
    [
        LinkRecord(id=None, long_url="", short_url="s", service="svc", created_at_utc=None),
        LinkRecord(id=None, long_url="x", short_url="", service="svc", created_at_utc=None),
        LinkRecord(id=None, long_url="x", short_url="s", service="", created_at_utc=None),
    ],
)
def test_add_invalid_record_raises(db_session, bad_record):
    svc = SqlAlchemyHistoryService()

    with pytest.raises(ValidationError):
        svc.add(bad_record)


def make_export_spec():
    return ExportSpec(
        filters=HistoryFilters(),
        sort=SortSpec(),
        locale="en",
        filename_suggestion="test.csv",
    )


def test_export_csv_empty_db(db_session):
    svc = SqlAlchemyHistoryService()

    spec = make_export_spec()
    data = svc.export_csv(spec)

    # декодируем CSV
    content = data.decode("utf-8").strip().splitlines()
    reader = csv.reader(content)

    rows = list(reader)
    # только заголовок
    assert rows[0] == ["created_at_utc", "service", "long_url", "short_url", "copy_count"]
    assert len(rows) == 1


def test_export_csv_with_record(db_session):
    svc = SqlAlchemyHistoryService()

    rec = LinkRecord(
        id=None,
        long_url="https://csvtest.com",
        short_url="csv1",
        service="CSV",
        created_at_utc=datetime.now(UTC),
        copy_count=42,
    )
    svc.add(rec)

    spec = make_export_spec()
    data = svc.export_csv(spec)

    content = data.decode("utf-8").strip().splitlines()
    reader = csv.reader(content)
    rows = list(reader)

    # первая строка — заголовки
    assert rows[0] == ["created_at_utc", "service", "long_url", "short_url", "copy_count"]
    # вторая строка — наши данные
    assert rows[1][1:] == ["CSV", "https://csvtest.com", "csv1", "42"]


def test_export_csv_sanitize_values(db_session):
    svc = SqlAlchemyHistoryService()

    # добавим значения, которые требуют экранирования
    rec = LinkRecord(
        id=None,
        long_url="=HACK",
        short_url="+evil",
        service="@bad",
        created_at_utc=datetime.now(UTC),
        copy_count=1,
    )
    svc.add(rec)

    spec = make_export_spec()
    data = svc.export_csv(spec)

    content = data.decode("utf-8").strip().splitlines()
    reader = csv.reader(content)
    rows = list(reader)

    # проверяем, что значения экранированы
    assert rows[1][1] == "'@bad"
    assert rows[1][2] == "'=HACK"
    assert rows[1][3] == "'+evil"


def test_apply_filters_by_service(db_session):
    svc = SqlAlchemyHistoryService()

    svc.add(LinkRecord(id=None, long_url="https://a.com", short_url="a", service="SVC1", created_at_utc=None))
    svc.add(LinkRecord(id=None, long_url="https://b.com", short_url="b", service="SVC2", created_at_utc=None))

    page = svc.list(
        filters=HistoryFilters(service="SVC1"),
        sort=SortSpec(),
        page=PageSpec(page=1, page_size=10),
    )
    assert all(item.service == "SVC1" for item in page.items)


def test_apply_filters_by_query(db_session):
    svc = SqlAlchemyHistoryService()

    svc.add(
        LinkRecord(id=None, long_url="https://example.com/hello", short_url="q123", service="Q", created_at_utc=None)
    )
    svc.add(LinkRecord(id=None, long_url="https://other.com", short_url="zzz", service="Q", created_at_utc=None))

    page = svc.list(
        filters=HistoryFilters(query="hello"),
        sort=SortSpec(),
        page=PageSpec(page=1, page_size=10),
    )
    assert any("hello" in item.long_url for item in page.items)
    assert all("hello" in item.long_url or "hello" in item.short_url for item in page.items)


def test_apply_filters_by_service_and_query(db_session):
    svc = SqlAlchemyHistoryService()

    svc.add(LinkRecord(id=None, long_url="https://a.com/hello", short_url="a1", service="SVC1", created_at_utc=None))
    svc.add(LinkRecord(id=None, long_url="https://b.com", short_url="bbb", service="SVC2", created_at_utc=None))

    # фильтр по service
    page = svc.list(
        filters=HistoryFilters(service="SVC1"),
        sort=SortSpec(),
        page=PageSpec(page=1, page_size=10),
    )
    assert all(item.service == "SVC1" for item in page.items)

    # фильтр по query
    page_q = svc.list(
        filters=HistoryFilters(query="hello"),
        sort=SortSpec(),
        page=PageSpec(page=1, page_size=10),
    )
    urls = [it.long_url for it in page_q.items]
    assert any("hello" in u for u in urls)


def test_utc_boundaries_from_local_dates_behavior():
    d1 = date.today()
    start, end = _utc_boundaries_from_local_dates(d1, d1)

    assert start is not None and end is not None
    # начало дня всегда <= конец дня
    assert start < end
    # проверяем, что границы охватывают примерно 24 часа
    delta = end - start
    assert delta.days in {0, 1}
    assert delta.total_seconds() >= 86399  # почти сутки


def test_utc_boundaries_none_args():
    start, end = _utc_boundaries_from_local_dates(None, None)
    assert start is None and end is None


def test_apply_filters_all_and_none(db_session):
    svc = SqlAlchemyHistoryService()

    # filters=None → не должно падать
    page = svc.list(
        filters=None,
        sort=SortSpec(),
        page=PageSpec(page=1, page_size=10),
    )
    assert isinstance(page.items, list)

    # service="ALL" → фильтр по сервису не применяется
    rec = LinkRecord(
        id=None,
        long_url="https://svc.com",
        short_url="svc",
        service="SVCALL",
        created_at_utc=None,
    )
    svc.add(rec)

    page2 = svc.list(
        filters=HistoryFilters(service="ALL"),
        sort=SortSpec(),
        page=PageSpec(page=1, page_size=10),
    )
    assert any(item.service == "SVCALL" for item in page2.items)


@pytest.mark.parametrize("bad_id", [0, -1])
def test_increment_copy_count_invalid_id(db_session, bad_id):
    svc = SqlAlchemyHistoryService()
    with pytest.raises(ValidationError):
        svc.increment_copy_count(bad_id)


def test_increment_copy_count_not_found(db_session):
    svc = SqlAlchemyHistoryService()
    with pytest.raises(NotFoundError):
        svc.increment_copy_count(99999)  # заведомо нет такого id


@pytest.mark.parametrize("bad_id", [0, -5])
def test_delete_invalid_id(db_session, bad_id):
    svc = SqlAlchemyHistoryService()
    with pytest.raises(ValidationError):
        svc.delete(bad_id)


def test_export_csv_invalid_sort(db_session):
    svc = SqlAlchemyHistoryService()

    bad_spec = ExportSpec(
        filters=HistoryFilters(),
        sort=SortSpec(field="bad_field"),  # type: ignore[arg-type]
        locale="en",
        filename_suggestion="bad.csv",
    )

    with pytest.raises(ValidationError):
        svc.export_csv(bad_spec)


def test_add_raises_storage_error(monkeypatch):
    svc = SqlAlchemyHistoryService()

    def bad_session(*args, **kwargs):
        raise SQLAlchemyError("db fail")

    monkeypatch.setattr("urlcutter.db.repo.history_sql.get_session", bad_session)

    rec = LinkRecord(id=None, long_url="x", short_url="y", service="z", created_at_utc=None)
    with pytest.raises(StorageError):
        svc.add(rec)


@pytest.mark.parametrize(
    "method,args",
    [
        ("list", [HistoryFilters(), SortSpec(), PageSpec(page=1, page_size=10)]),
        ("increment_copy_count", [1]),
        ("delete", [1]),
        (
            "export_csv",
            [ExportSpec(filters=HistoryFilters(), sort=SortSpec(), locale="en", filename_suggestion="x.csv")],
        ),
    ],
)
def test_methods_raise_storage_error(monkeypatch, method, args):
    svc = SqlAlchemyHistoryService()

    def bad_session(*a, **kw):
        raise SQLAlchemyError("boom")

    monkeypatch.setattr("urlcutter.db.repo.history_sql.get_session", bad_session)

    with pytest.raises(StorageError):
        getattr(svc, method)(*args)
