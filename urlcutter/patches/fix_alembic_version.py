import importlib
import importlib.metadata

try:
    # пытаемся импортировать Alembic только если он реально есть
    alembic = importlib.import_module("alembic")
    try:
        alembic.__version__ = importlib.metadata.version("alembic")
    except Exception:
        alembic.__version__ = "unknown"
except ModuleNotFoundError:
    # если Alembic вообще не установлен — делаем заглушку
    class DummyAlembic:
        __version__ = "not-installed"

    alembic = DummyAlembic()
