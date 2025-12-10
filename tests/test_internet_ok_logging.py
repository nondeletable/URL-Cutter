import logging

import pytest

from lite_upgrade import internet_ok


class FakeLogger:
    def __init__(self):
        self._logger = logging.getLogger("test.internet_ok")
        self._logger.setLevel(logging.DEBUG)
        self.records = []

        class _H(logging.Handler):
            def __init__(self, outer):
                super().__init__()
                self.outer = outer

            def emit(self, rec):
                self.outer.records.append(rec)

        self._logger.addHandler(_H(self))

    def debug(self, *a, **k):
        self._logger.debug(*a, **k)

    def info(self, *a, **k):
        self._logger.info(*a, **k)

    def warning(self, *a, **k):
        self._logger.warning(*a, **k)

    def error(self, *a, **k):
        self._logger.error(*a, **k)


@pytest.fixture
def logger():
    return FakeLogger()


def test_internet_ok_logs_when_circuit_open(monkeypatch, logger):
    class FakeAppState:
        def circuit_blocked(self):
            return True

        def rate_limit_allow(self, _):
            pytest.fail("should not call rate_limit_allow")

    monkeypatch.setattr("lite_upgrade.AppState", FakeAppState)

    assert internet_ok(logger) is False
    msgs = [r.getMessage() for r in logger.records]
    assert any("circuit" in m.lower() for m in msgs)


def test_internet_ok_logs_when_rate_limited(monkeypatch, logger):
    class FakeAppState:
        def circuit_blocked(self):
            return False

        def rate_limit_allow(self, _):
            return False

    monkeypatch.setattr("lite_upgrade.AppState", FakeAppState)

    assert internet_ok(logger) is False
    msgs = [r.getMessage() for r in logger.records]
    assert any("rate" in m.lower() and "limit" in m.lower() for m in msgs)
