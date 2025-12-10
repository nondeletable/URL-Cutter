import pytest

from urlcutter.db.repo.history_service import HistoryService
from urlcutter.db.repo.schemas import ExportSpec, HistoryFilters, LinkRecord, PageSpec, SortSpec


class DummyHistoryService(HistoryService):
    def list(self, filters, sort, page):
        return super().list(filters, sort, page)

    def add(self, record):
        return super().add(record)

    def increment_copy_count(self, id: int):
        return super().increment_copy_count(id)

    def delete(self, id: int):
        return super().delete(id)

    def export_csv(self, spec):
        return super().export_csv(spec)

    def distinct_services(self):
        return super().distinct_services()


def test_abstract_methods_raise():
    svc = DummyHistoryService()

    with pytest.raises(NotImplementedError):
        svc.list(HistoryFilters(), SortSpec(), PageSpec(page=1, page_size=10))

    with pytest.raises(NotImplementedError):
        svc.add(LinkRecord(id=None, long_url="x", short_url="y", service="z", created_at_utc=None))

    with pytest.raises(NotImplementedError):
        svc.increment_copy_count(1)

    with pytest.raises(NotImplementedError):
        svc.delete(1)

    with pytest.raises(NotImplementedError):
        svc.export_csv(ExportSpec(filters=HistoryFilters(), sort=SortSpec(), locale="en", filename_suggestion="f.csv"))

    with pytest.raises(NotImplementedError):
        svc.distinct_services()
