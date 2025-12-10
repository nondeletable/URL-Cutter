import pytest

import lite_upgrade


def test_shorten_timeout(monkeypatch):
    # эмулируем таймаут у ThreadPoolExecutor.result()
    class FakeFuture:
        def result(self, timeout):
            raise lite_upgrade.FutTimeout()

    class FakeExecutor:
        def __init__(self, max_workers):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def submit(self, fn):  # fn не вызываем, сразу "таймаут"
            return FakeFuture()

    monkeypatch.setattr(lite_upgrade, "ThreadPoolExecutor", FakeExecutor)

    with pytest.raises(lite_upgrade.FutTimeout):
        lite_upgrade.shorten_via_tinyurl("http://example.com", timeout=0.01)
