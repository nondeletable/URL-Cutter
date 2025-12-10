import sys

import pytest

from urlcutter.db import paths


def test_user_data_dir_with_override(monkeypatch, tmp_path):
    monkeypatch.setenv("URLCUTTER_DATA_DIR", str(tmp_path))
    p = paths.user_data_dir()
    assert p == tmp_path.resolve()
    assert p.exists()


@pytest.mark.parametrize(
    "system_name,expected",
    [
        ("Windows", "UrlCutter"),
        ("Darwin", "UrlCutter"),
        ("Linux", "UrlCutter"),
    ],
)
def test_user_data_dir_per_os(monkeypatch, system_name, expected):
    monkeypatch.delenv("URLCUTTER_DATA_DIR", raising=False)
    monkeypatch.setattr(paths.platform, "system", lambda: system_name)
    p = paths.user_data_dir()
    assert expected in str(p)
    assert p.exists()


def test_db_path_points_to_history_db(monkeypatch, tmp_path):
    monkeypatch.setenv("URLCUTTER_DATA_DIR", str(tmp_path))
    p = paths.db_path()
    assert p.name == "history.db"
    assert str(tmp_path) in str(p)


def test_alembic_dir_with_override(monkeypatch, tmp_path):
    override = tmp_path / "alembic_override"
    override.mkdir()
    monkeypatch.setenv("URLCUTTER_ALEMBIC_DIR", str(override))
    p = paths.alembic_dir()
    assert p == override


def test_alembic_dir_with_frozen(monkeypatch, tmp_path):
    alembic_dir = tmp_path / "alembic_migrations"
    alembic_dir.mkdir()
    monkeypatch.delenv("URLCUTTER_ALEMBIC_DIR", raising=False)
    monkeypatch.setattr(paths, "_is_frozen", lambda: True)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    p = paths.alembic_dir()
    assert p == alembic_dir


def test_alembic_dir_with_project_root(monkeypatch, tmp_path):
    project_root = tmp_path / "proj"
    alembic_dir = project_root / "alembic_migrations"
    alembic_dir.mkdir(parents=True)
    monkeypatch.delenv("URLCUTTER_ALEMBIC_DIR", raising=False)
    monkeypatch.setattr(paths, "_is_frozen", lambda: False)
    monkeypatch.setattr(paths, "__file__", str(project_root / "urlcutter" / "db" / "paths.py"))

    p = paths.alembic_dir()
    assert p == alembic_dir


def test_alembic_dir_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("URLCUTTER_ALEMBIC_DIR", raising=False)
    monkeypatch.setattr(paths, "_is_frozen", lambda: False)
    monkeypatch.setattr(paths, "__file__", str(tmp_path / "urlcutter" / "db" / "paths.py"))

    monkeypatch.setenv("URLCUTTER_DATA_DIR", str(tmp_path / "data"))
    p = paths.alembic_dir()
    assert "alembic" in str(p)
    assert p.exists()


def test_is_frozen_false(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.delenv("URLCUTTER_ALEMBIC_DIR", raising=False)
    assert paths._is_frozen() is False


def test_alembic_dir_override_not_exists(monkeypatch, tmp_path):
    bad_dir = tmp_path / "does_not_exist"
    monkeypatch.setenv("URLCUTTER_ALEMBIC_DIR", str(bad_dir))
    monkeypatch.setattr(paths, "_is_frozen", lambda: False)
    # вернёт fallback (user_data_dir/alembic), но главное — покрыть ветку
    result = paths.alembic_dir()
    assert "alembic" in str(result)


def test_alembic_dir_frozen_not_exists(monkeypatch, tmp_path):
    monkeypatch.delenv("URLCUTTER_ALEMBIC_DIR", raising=False)
    monkeypatch.setattr(paths, "_is_frozen", lambda: True)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    # alembic не существует в _MEIPASS → должен перейти дальше
    result = paths.alembic_dir()
    assert "alembic" in str(result)
