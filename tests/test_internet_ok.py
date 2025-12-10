import pytest

from lite_upgrade import internet_ok


# Минимальный логгер, чтобы удовлетворить сигнатуры
class FakeLogger:
    def debug(self, *a, **k):
        pass

    def info(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


@pytest.fixture
def logger():
    return FakeLogger()


def test_internet_ok_false_when_circuit_blocked(monkeypatch, logger):
    class FakeAppState:
        def __init__(self):
            pass

        def circuit_blocked(self) -> bool:
            return True

        def rate_limit_allow(self, logger) -> bool:  # не должен вызываться, но пусть будет
            pytest.fail("rate_limit_allow must not be called when circuit is blocked")

    # подменяем КЛАСС AppState в модуле lite_upgrade
    monkeypatch.setattr("lite_upgrade.AppState", FakeAppState)

    assert internet_ok(logger) is False


def test_internet_ok_false_when_rate_limit_disallows(monkeypatch, logger):
    class FakeAppState:
        def __init__(self):
            pass

        def circuit_blocked(self) -> bool:
            return False

        def rate_limit_allow(self, logger) -> bool:
            return False

    monkeypatch.setattr("lite_upgrade.AppState", FakeAppState)

    assert internet_ok(logger) is False


def test_internet_ok_true_when_all_good(monkeypatch, logger):
    class FakeAppState:
        def __init__(self):
            pass

        def circuit_blocked(self) -> bool:
            return False

        def rate_limit_allow(self, logger) -> bool:
            return True

    monkeypatch.setattr("lite_upgrade.AppState", FakeAppState)

    assert internet_ok(logger) is True
