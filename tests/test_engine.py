import pytest
from sqlalchemy import text

from urlcutter.db import engine


def test_get_session_commit(tmp_path, monkeypatch):
    # перенаправляем БД в tmp_path, чтобы не трогать реальную
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(engine, "_SQLITE_URL", f"sqlite:///{db_file}")
    engine.engine.dispose()
    new_engine = engine.create_engine(engine._SQLITE_URL, connect_args={"check_same_thread": False}, future=True)
    monkeypatch.setattr(engine, "engine", new_engine)
    monkeypatch.setattr(
        engine, "SessionLocal", engine.sessionmaker(bind=new_engine, autoflush=False, autocommit=False, future=True)
    )

    with engine.get_session() as s:
        res = s.execute(text("SELECT 1")).scalar_one()
        assert res == 1


def test_get_session_rollback(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(engine, "_SQLITE_URL", f"sqlite:///{db_file}")
    engine.engine.dispose()
    new_engine = engine.create_engine(engine._SQLITE_URL, connect_args={"check_same_thread": False}, future=True)
    monkeypatch.setattr(engine, "engine", new_engine)
    monkeypatch.setattr(
        engine, "SessionLocal", engine.sessionmaker(bind=new_engine, autoflush=False, autocommit=False, future=True)
    )

    class CustomError(Exception):
        pass

    with pytest.raises(CustomError), engine.get_session() as s:
        s.execute(text("SELECT 1"))
        raise CustomError("force rollback")
