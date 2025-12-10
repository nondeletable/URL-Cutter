import pytest

from lite_upgrade import AppState
from urlcutter.protection import (
    CB_COOLDOWN_SEC,
    CB_FAIL_THRESHOLD,
    CLIENT_RPM_LIMIT,
    _reset_state,  # служебные, только для тестов
    circuit_blocked,
    cooldown_left,
    rate_limit_allow,
    record_failure,
    record_success,
)

# --- ВСПОМОГАТЕЛЬНОЕ ---


class FakeLogger:
    def __init__(self):
        self.messages = []

    def debug(self, *a, **k):
        self.messages.append(("DEBUG", a, k))

    def info(self, *a, **k):
        self.messages.append(("INFO", a, k))

    def warning(self, *a, **k):
        self.messages.append(("WARN", a, k))

    def error(self, *a, **k):
        self.messages.append(("ERROR", a, k))


@pytest.fixture
def logger():
    return FakeLogger()


@pytest.fixture
def fake_time(monkeypatch):
    # Контролируем time.time()
    t = {"now": 1_000_000.0}

    def _time():
        return t["now"]

    def _sleep(dt):
        t["now"] += dt

    monkeypatch.setattr("time.time", _time)
    monkeypatch.setattr("time.sleep", _sleep)  # на случай, если используется
    return t


@pytest.fixture
def app():
    # Чистый экземпляр без «грязного» состояния между тестами
    return AppState()


# --- RATE LIMIT ---


def test_rate_limit_allow_under_limit(app, logger):
    # Первые несколько вызовов должны быть True (точное число не важно)
    # Проверим хотя бы 3, чтобы поймать ранние ошибки.
    assert app.rate_limit_allow(logger) is True
    assert app.rate_limit_allow(logger) is True
    assert app.rate_limit_allow(logger) is True


def test_rate_limit_blocks_and_recovers(app, logger, fake_time):
    # Дожимаем до блокировки, не зная констант (с защитой от бесконечного цикла)
    blocked_at = None
    for i in range(1, 200):
        if app.rate_limit_allow(logger) is False:
            blocked_at = i
            break
    assert blocked_at is not None, "не удалось вызвать блокировку rate-limit до 200 вызовов"

    # Сразу после блокировки — всё ещё False
    assert app.rate_limit_allow(logger) is False

    # Сдвигаем окно на ~60 секунд и проверяем, что снова разрешает
    fake_time["now"] += 61
    assert app.rate_limit_allow(logger) is True


# --- CIRCUIT BREAKER ---


def test_circuit_opens_after_enough_failures(app):
    # Накапливаем failures, пока не откроется цепь
    opened_on = None
    for i in range(1, 50):
        app.record_failure()
        if app.circuit_blocked():
            opened_on = i
            break
    assert opened_on is not None, "цепь не открылась после серии ошибок"
    assert app.cooldown_left() > 0


def test_circuit_half_open_after_cooldown(app, fake_time):
    # Открыли цепь
    for _ in range(10):
        app.record_failure()
        if app.circuit_blocked():
            break
    assert app.circuit_blocked() is True

    # Ждём истечения кулдауна (сколько именно — берём из метода)
    wait = app.cooldown_left()
    # иногда метод возвращает int, иногда float — не принципиально
    if wait and wait > 0:
        fake_time["now"] += wait + 0.001

    # После кулдауна блокировка должна сняться (half-open/allow)
    assert app.circuit_blocked() is False


def test_circuit_closes_on_success_after_cooldown(app, fake_time):
    # Открыли
    for _ in range(10):
        app.record_failure()
        if app.circuit_blocked():
            break
    assert app.circuit_blocked() is True

    # Дождались конца кулдауна
    wait = app.cooldown_left()
    fake_time["now"] += (wait or 0) + 0.001

    # Один успех должен «закрыть» цепь (сбросить состояние)
    app.record_success()
    assert app.circuit_blocked() is False


def test_sparse_failures_do_not_open_circuit(app):
    # Разреженные ошибки не должны открыть цепь
    app.record_failure()
    app.record_success()
    app.record_failure()
    assert app.circuit_blocked() is False


class FakeClock:
    def __init__(self, start=1_000_000.0):
        self.t = float(start)

    def now(self):
        return self.t

    def tick(self, sec):
        self.t += sec


@pytest.fixture(autouse=True)
def clean_state():
    _reset_state()
    yield
    _reset_state()


def test_rate_limit_basic_window():
    clk = FakeClock()
    # Разрешаем до лимита включительно
    for _i in range(CLIENT_RPM_LIMIT):
        assert rate_limit_allow(now_fn=clk.now)
    # Следующий запрос должен быть заблокирован
    assert not rate_limit_allow(now_fn=clk.now)
    # Через 61 сек окно сдвинется — снова можно
    clk.tick(61)
    assert rate_limit_allow(now_fn=clk.now)


def test_circuit_opens_on_fail_threshold():
    clk = FakeClock()
    # До порога — не блокируем
    for _ in range(CB_FAIL_THRESHOLD - 1):
        record_failure(now_fn=clk.now)
        assert not circuit_blocked(now_fn=clk.now)
    # На пороге — должен открыться
    record_failure(now_fn=clk.now)
    assert circuit_blocked(now_fn=clk.now)
    assert cooldown_left(now_fn=clk.now) == CB_COOLDOWN_SEC


def test_circuit_counts_down_and_closes():
    clk = FakeClock()
    for _ in range(CB_FAIL_THRESHOLD):
        record_failure(now_fn=clk.now)
    assert circuit_blocked(now_fn=clk.now)
    # Идёт отсчёт
    clk.tick(CB_COOLDOWN_SEC - 1)
    assert circuit_blocked(now_fn=clk.now)
    assert cooldown_left(now_fn=clk.now) == 1
    # Прошли все секунды — закрыто
    clk.tick(1)
    assert not circuit_blocked(now_fn=clk.now)
    assert cooldown_left(now_fn=clk.now) == 0


def test_record_success_resets_fail_counter():
    clk = FakeClock()
    for _ in range(CB_FAIL_THRESHOLD - 1):
        record_failure(now_fn=clk.now)
    record_success()
    # Снова набираем — порог должен считаться от нуля
    for _ in range(CB_FAIL_THRESHOLD - 1):
        record_failure(now_fn=clk.now)
        assert not circuit_blocked(now_fn=clk.now)
    record_failure(now_fn=clk.now)
    assert circuit_blocked(now_fn=clk.now)


def test_mixed_rate_limit_and_circuit_independent():
    clk = FakeClock()
    # Забьём rate-limit
    for _ in range(CLIENT_RPM_LIMIT):
        assert rate_limit_allow(now_fn=clk.now)
    assert not rate_limit_allow(now_fn=clk.now)
    # Параллельно откроем «предохранитель»
    for _ in range(CB_FAIL_THRESHOLD):
        record_failure(now_fn=clk.now)
    assert circuit_blocked(now_fn=clk.now)
    # Промотаем > минуту и > cooldown — оба должны «отпустить»
    clk.tick(max(61, CB_COOLDOWN_SEC + 1))
    assert rate_limit_allow(now_fn=clk.now)
    assert not circuit_blocked(now_fn=clk.now)
