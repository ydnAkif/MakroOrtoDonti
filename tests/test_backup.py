from __future__ import annotations

import argparse
import sqlite3
from contextlib import closing

import backup


def _create_database(path, value="original"):
    with closing(sqlite3.connect(path)) as connection:
        with connection:
            connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
            connection.execute("INSERT INTO sample VALUES (?)", (value,))


def _database_url(path):
    return f"sqlite:///{path}"


def test_backup_rotation_verify_and_restore(tmp_path, monkeypatch):
    db_path = tmp_path / "active.db"
    _create_database(db_path)
    monkeypatch.setenv("DATABASE_URL", _database_url(db_path))

    for _ in range(3):
        assert backup.cmd_backup(argparse.Namespace(keep=2)) == 0

    backups = sorted((tmp_path / "backups").glob(backup.BACKUP_PATTERN))
    assert len(backups) == 2
    assert backup.cmd_verify(argparse.Namespace(file=str(backups[-1]))) == 0

    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            connection.execute("UPDATE sample SET value = 'changed'")

    assert backup.cmd_restore(
        argparse.Namespace(file=str(backups[-1]), yes=True)
    ) == 0
    with closing(sqlite3.connect(db_path)) as connection:
        assert connection.execute("SELECT value FROM sample").fetchone()[0] == "original"
    assert list(tmp_path.glob("active.pre-restore-*.db"))


def test_restore_requires_explicit_confirmation(tmp_path, monkeypatch):
    db_path = tmp_path / "active.db"
    source = tmp_path / "source.db"
    _create_database(db_path)
    _create_database(source, value="replacement")
    monkeypatch.setenv("DATABASE_URL", _database_url(db_path))

    assert backup.cmd_restore(argparse.Namespace(file=str(source), yes=False)) == 2
    with closing(sqlite3.connect(db_path)) as connection:
        assert connection.execute("SELECT value FROM sample").fetchone()[0] == "original"


def test_backup_rejects_non_sqlite_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/example")
    assert backup.cmd_backup(argparse.Namespace(keep=2)) == 2
