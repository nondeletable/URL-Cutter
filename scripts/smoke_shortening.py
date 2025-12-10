# быстрый смоук без сети: подмена провайдера и вызов ядра
import lite_upgrade


class FakeTiny:
    def short(self, u):
        return "https://tinyurl.com/smoke"


class FakeShortener:
    def __init__(self):
        self.tinyurl = FakeTiny()


lite_upgrade.pyshorteners.Shortener = lambda: FakeShortener()

print(lite_upgrade.shorten_via_tinyurl("http://example.com", timeout=0.1))
