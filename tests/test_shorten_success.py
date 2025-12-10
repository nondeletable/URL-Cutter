import lite_upgrade


def test_shorten_success(monkeypatch):
    # подменяем pyshorteners.Shortener() на фейк
    class FakeTiny:
        def short(self, u):  # имитируем успешный ответ сервиса
            return "https://tinyurl.com/abc123"

    class FakeShortener:
        def __init__(self):
            self.tinyurl = FakeTiny()

    monkeypatch.setattr(lite_upgrade.pyshorteners, "Shortener", lambda: FakeShortener())

    out = lite_upgrade.shorten_via_tinyurl("http://example.com", timeout=0.1)
    assert out.startswith("https://tinyurl.com/")
