from .logging_utils import setup_logging
from .normalization import _url_fingerprint, normalize_url
from .protection import (
    CB_COOLDOWN_SEC,
    CB_FAIL_THRESHOLD,
    CIRCUIT_COOLDOWN_SEC,
    CIRCUIT_FAIL_THRESHOLD,
    CLIENT_RPM_LIMIT,
    RATE_LIMIT_WINDOW_SEC,
    AppState,
    _get_state,
    _reset_state,
    circuit_blocked,
    cooldown_left,
    internet_ok,
    rate_limit_allow,
    record_failure,
    record_success,
)
from .shorteners import shorten_via_tinyurl_core

__all__ = [
    "normalize_url",
    "_url_fingerprint",
    "setup_logging",
    "CB_COOLDOWN_SEC",
    "CB_FAIL_THRESHOLD",
    "CIRCUIT_COOLDOWN_SEC",
    "CIRCUIT_FAIL_THRESHOLD",
    "CLIENT_RPM_LIMIT",
    "RATE_LIMIT_WINDOW_SEC",
    "AppState",
    "_get_state",
    "_reset_state",
    "circuit_blocked",
    "cooldown_left",
    "internet_ok",
    "rate_limit_allow",
    "record_failure",
    "record_success",
    "shorten_via_tinyurl_core",
]
__version__ = "0.1.0"
