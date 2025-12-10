"""SQLAlchemy-backed implementation of HistoryService."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, time

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError

from urlcutter.db.engine import get_session
from urlcutter.db.models import Link
from urlcutter.db.repo.errors import ExportError, NotFoundError, StorageError, ValidationError
from urlcutter.db.repo.history_service import HistoryService
from urlcutter.db.repo.schemas import (
    ExportSpec,
    HistoryFilters,
    HistoryPage,
    LinkRecord,
    PageSpec,
    SortSpec,
)


def _utc_boundaries_from_local_dates(date_from_local, date_to_local) -> tuple[datetime | None, datetime | None]:
    """date -> [00:00, 23:59:59.999999] в ЛОКАЛИ, затем в UTC."""
    if not (date_from_local or date_to_local):
        return None, None

    tz = datetime.now().astimezone().tzinfo  # локальная TZ машины
    start_utc = (
        datetime.combine(date_from_local, time.min).replace(tzinfo=tz).astimezone(UTC) if date_from_local else None
    )
    end_utc = datetime.combine(date_to_local, time.max).replace(tzinfo=tz).astimezone(UTC) if date_to_local else None
    return start_utc, end_utc


def _sanitize_csv_value(v: str) -> str:
    """Защита от CSV-инъекций."""
    if not v:
        return v
    if v[0] in ("=", "+", "-", "@"):
        return "'" + v
    return v


class SqlAlchemyHistoryService(HistoryService):
    """Конкретная реализация HistoryService на SQLAlchemy."""

    _SORT_MAP = {
        "created_at": Link.created_at,
        "created_at_utc": Link.created_at,  # ← алиас, чтобы UI мог прислать оба варианта
        "service": Link.service,
        "long_url": Link.long_url,
        "short_url": Link.short_url,
        "copy_count": Link.copy_count,
    }

    # ---------- helpers ----------

    def _apply_filters(self, stmt, filters: HistoryFilters):
        if filters is None:
            return stmt

        # service
        if filters.service and filters.service != "ALL":
            stmt = stmt.where(Link.service == filters.service)

        # dates (inclusive)
        start_utc, end_utc = _utc_boundaries_from_local_dates(filters.date_from_local, filters.date_to_local)
        if start_utc:
            stmt = stmt.where(Link.created_at >= start_utc.replace(tzinfo=None))
        if end_utc:
            stmt = stmt.where(Link.created_at <= end_utc.replace(tzinfo=None))

        # query (CI substring in long OR short)
        if filters.query:
            q = f"%{filters.query.lower()}%"
            stmt = stmt.where(or_(func.lower(Link.long_url).like(q), func.lower(Link.short_url).like(q)))
        return stmt

    # ---------- interface ----------

    def list(self, filters: HistoryFilters, sort: SortSpec, page: PageSpec) -> HistoryPage:
        if page.page < 1 or page.page_size <= 0:
            raise ValidationError("Invalid page or page_size")

        order_col = self._SORT_MAP.get(sort.field)
        if order_col is None:
            raise ValidationError(f"Unknown sort field: {sort.field}")
        order_expr = order_col.desc() if sort.direction == "desc" else order_col.asc()

        try:
            with get_session() as s:
                # ключ: отключаем протухание атрибутов на коммите
                s.expire_on_commit = False

                base = select(Link)
                base = self._apply_filters(base, filters)

                total = s.execute(select(func.count()).select_from(base.subquery())).scalar_one()

                stmt = base.order_by(order_expr).offset((page.page - 1) * page.page_size).limit(page.page_size)
                rows = s.execute(stmt).scalars().all()

                # СБОР ДАННЫХ ВНУТРИ СЕССИИ
                items = [
                    LinkRecord(
                        id=r.id,
                        long_url=r.long_url or "",
                        short_url=r.short_url or "",
                        service=r.service or "",
                        created_at_utc=r.created_at,
                        copy_count=r.copy_count or 0,
                    )
                    for r in rows
                ]

            has_prev = page.page > 1
            has_next = (page.page * page.page_size) < total
            return HistoryPage(
                items=items, total=total, page=page.page, page_size=page.page_size, has_prev=has_prev, has_next=has_next
            )
        except SQLAlchemyError as e:
            raise StorageError(str(e)) from e

    def add(self, record: LinkRecord) -> LinkRecord:
        if not record.long_url or not record.short_url or not record.service:
            raise ValidationError("long_url, short_url, service are required")

        try:
            with get_session() as s:
                obj = Link(
                    long_url=record.long_url,
                    short_url=record.short_url,
                    service=record.service,
                    # created_at по умолчанию в модели
                    copy_count=record.copy_count or 0,
                )
                s.add(obj)
                s.flush()  # получаем id и created_at
                s.commit()  # << вот этого раньше не было
                stored = LinkRecord(
                    id=obj.id,
                    long_url=obj.long_url,
                    short_url=obj.short_url,
                    service=obj.service,
                    created_at_utc=obj.created_at,
                    copy_count=obj.copy_count,
                )
                return stored
        except SQLAlchemyError as e:
            raise StorageError(str(e)) from e

    def increment_copy_count(self, id: int) -> None:
        if not isinstance(id, int) or id <= 0:
            raise ValidationError("Invalid id")
        try:
            with get_session() as s:
                obj = s.get(Link, id)
                if not obj:
                    raise NotFoundError(f"id={id} not found")
                obj.copy_count += 1
                s.commit()
        except SQLAlchemyError as e:
            raise StorageError(str(e)) from e

    def delete(self, id: int) -> bool:
        if not isinstance(id, int) or id <= 0:
            raise ValidationError("Invalid id")
        try:
            with get_session() as s:
                obj = s.get(Link, id)
                if not obj:
                    return False
                s.delete(obj)
                s.commit()  # ← этот commit оставляем
                return True
        except SQLAlchemyError as e:
            raise StorageError(str(e)) from e

    def export_csv(self, spec: ExportSpec) -> bytes:
        # выгружаем всю выборку по фильтрам/сортировке
        order_col = self._SORT_MAP.get(spec.sort.field)
        if order_col is None:
            raise ValidationError(f"Unknown sort field: {spec.sort.field}")
        order_expr = order_col.desc() if spec.sort.direction == "desc" else order_col.asc()

        try:
            with get_session() as s:
                base = select(Link)
                base = self._apply_filters(base, spec.filters)
                stmt = base.order_by(order_expr)
                rows: list[Link] = s.execute(stmt).scalars().all()
        except SQLAlchemyError as e:
            raise StorageError(str(e)) from e

        buf = io.StringIO(newline="")
        writer = csv.writer(buf, delimiter=",", quoting=csv.QUOTE_MINIMAL)

        # заголовки
        writer.writerow(["created_at_utc", "service", "long_url", "short_url", "copy_count"])

        for r in rows:
            writer.writerow(
                [
                    (r.created_at or datetime.now(UTC).replace(tzinfo=None)).replace(microsecond=0).isoformat() + "Z",
                    _sanitize_csv_value(r.service),
                    _sanitize_csv_value(r.long_url),
                    _sanitize_csv_value(r.short_url),
                    r.copy_count,
                ]
            )

        try:
            return buf.getvalue().encode("utf-8")
        except Exception as e:  # noqa: BLE001
            raise ExportError(str(e)) from e

    def distinct_services(self) -> list[str]:
        try:
            with get_session() as s:
                stmt = select(Link.service).distinct().order_by(Link.service.asc())
                return [row[0] for row in s.execute(stmt).all() if row[0]]
        except SQLAlchemyError as e:
            raise StorageError(str(e)) from e
