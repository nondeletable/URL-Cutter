import logging

from lite_upgrade import setup_logging


def _levels(logger):
    lvl = logger.level
    # собираем уровни у хендлеров
    handlers = [h.level for h in logger.handlers]
    return lvl, handlers


def test_setup_logging_disabled_debug_off():
    lg = setup_logging(enabled=False, debug=False)
    # когда выключено — можно ожидать, что логер на WARNING/ERROR
    lvl, handlers = _levels(lg)
    assert lvl in (logging.WARNING, logging.ERROR, logging.CRITICAL)


def test_setup_logging_enabled_debug_off():
    lg = setup_logging(enabled=True, debug=False)
    lvl, handlers = _levels(lg)
    assert lvl <= logging.INFO  # INFO или ниже
    assert len(lg.handlers) >= 1


def test_setup_logging_enabled_debug_on():
    lg = setup_logging(enabled=True, debug=True)
    lvl, handlers = _levels(lg)
    assert lvl <= logging.DEBUG  # DEBUG или ниже
    assert len(lg.handlers) >= 1
