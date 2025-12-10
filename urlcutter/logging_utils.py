import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(  # noqa: PLR0913
    *,
    enabled: bool = True,
    debug: bool = False,
    logger_name: str = "urlcutter",
    file_path: str | None = "logs/app.log",
    max_bytes: int = 500_000,
    backups: int = 3,
) -> logging.Logger:
    """
    Настраивает логирование.
    - enabled=False: отключаем вывод (ставим NullHandler), уровень WARNING (или DEBUG, если debug=True).
    - enabled=True: добавляем StreamHandler и, если file_path не None, RotatingFileHandler.
    """
    logger = logging.getLogger(logger_name)

    # Чистим предыдущие хендлеры, чтобы при повторных вызовах не плодить дубликаты
    logger.handlers.clear()

    level = logging.DEBUG if debug else logging.INFO
    if not enabled:
        logger.setLevel(logging.DEBUG if debug else logging.WARNING)
        logger.addHandler(logging.NullHandler())
        return logger

    logger.setLevel(level)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    # Консоль
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # Файл (если указан путь)
    if file_path:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(file_path, maxBytes=max_bytes, backupCount=backups, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger
