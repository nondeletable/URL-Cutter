from concurrent.futures import TimeoutError
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from urlcutter.db.models import Base
from urlcutter.db.repo import history_sql


@pytest.fixture
def fake_shortener_ok_factory():
    # Возвращает КОНСТРУКТОР (нулеарг. callable), который даёт объект с .tinyurl.short(...)
    def _factory():
        class FakeTiny:
            def short(self, url: str) -> str:
                return "https://tiny.one/abc123"

        class FakeShortener:
            tinyurl = FakeTiny()

        return FakeShortener()

    return _factory


@pytest.fixture
def fake_shortener_boom_factory():
    def _factory():
        class FakeTiny:
            def short(self, url: str) -> str:
                raise RuntimeError("boom")

        class FakeShortener:
            tinyurl = FakeTiny()

        return FakeShortener()

    return _factory


@pytest.fixture
def fake_pool_timeout_factory():
    # Пул, у которого future.result(...) всегда кидает TimeoutError

    class FakeFuture:
        def result(self, timeout):
            raise TimeoutError()

    class FakePool:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def submit(self, fn, *args, **kwargs):
            return FakeFuture()

    # Возвращаем нулеарг. callable, чтобы выглядеть как ThreadPoolExecutor(max_workers=?)
    def _factory(*args, **kwargs):
        return FakePool()

    return _factory


@pytest.fixture
def fake_shortener_assert_not_called_factory():
    # Если функция вдруг полезет к провайдеру — тест упадёт сразу.
    def _factory():
        class FakeTiny:
            def short(self, url: str) -> str:
                raise AssertionError("Provider MUST NOT be called for invalid input")

        class FakeShortener:
            tinyurl = FakeTiny()

        return FakeShortener()

    return _factory


#  Провайдер, который проверяет, что ему пришёл именно ожидаемый (очищенный) URL
@pytest.fixture
def fake_shortener_expect_url_factory():
    def _factory(expected_url: str):
        class FakeTiny:
            def short(self, url: str) -> str:
                assert url == expected_url, f"expected {expected_url}, got {url!r}"
                return "https://tiny.one/abc123"

        class FakeShortener:
            tinyurl = FakeTiny()

        return FakeShortener()

    return _factory


# Пул, который сразу выполняет функцию и ЗАПОМИНАЕТ timeout,
#    чтобы мы могли проверить его значение в тесте
@pytest.fixture
def fake_pool_capturing_timeout_factory():
    captured = {"timeout": None, "calls": 0}

    class FakeFuture:
        def __init__(self, value):
            self._value = value

        def result(self, timeout):
            captured["timeout"] = timeout
            captured["calls"] += 1
            return self._value

    class FakePool:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def submit(self, fn, *args, **kwargs):
            # выполняем сразу и кладём результат во future
            return FakeFuture(fn(*args, **kwargs))

    def _factory():
        # возвращаем сам пул и словарь с захваченным таймаутом
        return FakePool(), captured

    return _factory


@pytest.fixture(scope="function")
def db_session():
    """Создаёт чистую in-memory SQLite БД для каждого теста."""
    engine = create_engine("sqlite:///:memory:", echo=False, future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(autouse=True)
def patch_get_session(monkeypatch, db_session):

    @contextmanager
    def fake_get_session():
        yield db_session

    monkeypatch.setattr(history_sql, "get_session", fake_get_session)
