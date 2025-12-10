import logging
import time
from collections import deque
from collections.abc import Callable

# --- Константы поведения ---
CLIENT_RPM_LIMIT = 60  # сколько запросов в минуту разрешено
CB_FAIL_THRESHOLD = 3  # после скольких подряд ошибок открываем предохранитель
CB_COOLDOWN_SEC = 30  # сколько секунд держим «открытым»
CIRCUIT_FAIL_THRESHOLD = 3  # сколько подряд ошибок, чтобы "остановиться"
CIRCUIT_COOLDOWN_SEC = 60  # на сколько секунд "остановиться" (cooldown)
RATE_LIMIT_WINDOW_SEC = 60

# --- Глобальное состояние (простое и прозрачное) ---
_state = {
    "ticks": deque(),  # таймстемпы успешных выдач для rate-limit
    "fail_count": 0,  # счётчик подряд идущих ошибок
    "cb_open_until": 0.0,  # unix-время, до которого предохранитель «открыт»
}


# Тестовые служебные функции (экспортируем для фикстур)
def _get_state():
    return _state


def _reset_state():
    _state["ticks"].clear()
    _state["fail_count"] = 0
    _state["cb_open_until"] = 0.0


class AppState:
    def __init__(self):
        self.ticks = deque(maxlen=CLIENT_RPM_LIMIT * 2)
        self.fails = 0
        self.blocked_until = 0.0

    def circuit_blocked(self) -> bool:
        return time.time() < self.blocked_until

    def record_failure(self):
        self.fails += 1
        if self.fails >= CIRCUIT_FAIL_THRESHOLD:
            self.blocked_until = time.time() + CIRCUIT_COOLDOWN_SEC

    def record_success(self):
        self.fails = 0
        self.blocked_until = 0.0

    def cooldown_left(self) -> int:
        return max(0, int(self.blocked_until - time.time()))

    def rate_limit_allow(self, logger: logging.Logger) -> bool:
        now = time.time()
        while self.ticks and now - self.ticks[0] > RATE_LIMIT_WINDOW_SEC:
            self.ticks.popleft()
        if len(self.ticks) >= CLIENT_RPM_LIMIT:
            logger.warning("rate_limit hit rpm=%d queue_len=%d", CLIENT_RPM_LIMIT, len(self.ticks))
            return False
        self.ticks.append(now)
        return True


def _now_default() -> float:
    return time.time()


def circuit_blocked(*, now_fn: Callable[[], float] = _now_default) -> bool:
    now = now_fn()
    return now < _state["cb_open_until"]


def cooldown_left(*, now_fn: Callable[[], float] = _now_default) -> int:
    now = now_fn()
    left = int(round(_state["cb_open_until"] - now))
    return max(0, left)


def record_failure(*, now_fn: Callable[[], float] = _now_default) -> None:
    now = now_fn()
    # Если уже открыт — просто обновим таймер (не обязательно, но удобно)
    if now < _state["cb_open_until"]:
        return
    _state["fail_count"] += 1
    if _state["fail_count"] >= CB_FAIL_THRESHOLD:
        _state["cb_open_until"] = now + CB_COOLDOWN_SEC
        _state["fail_count"] = 0  # сбросим, чтобы после окна считать заново


def record_success() -> None:
    # Любой успешный вызов сбрасывает счётчик ошибок
    _state["fail_count"] = 0


def rate_limit_allow(*, now_fn: Callable[[], float] = _now_default) -> bool:
    """
    Скользящее окно 60 сек: очищаем старые метки и решаем, можно ли ещё.
    """
    now = now_fn()
    # Очищаем старые записи старше 60с
    window_start = now - float(RATE_LIMIT_WINDOW_SEC)
    ticks = _state["ticks"]
    while ticks and ticks[0] <= window_start:
        ticks.popleft()
    if len(ticks) < CLIENT_RPM_LIMIT:
        ticks.append(now)
        return True
    return False


def internet_ok(logger: logging.Logger, *, AppState_cls=AppState) -> bool:
    st = AppState_cls()

    if st.circuit_blocked():
        logger.warning("circuit open: skip network")
        return False

    if not st.rate_limit_allow(logger):
        logger.warning("rate limit exceeded")
        return False

    return True
