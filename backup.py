#!/usr/bin/env python3
"""Consistent backup, verification, listing, and restore for the SQLite DB."""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import sqlite3
import sys
import tempfile
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from cryptography.fernet import Fernet, InvalidToken


PROJECT_ROOT = Path(__file__).resolve().parent
BACKUP_PATTERN = "makroortodonti_*.db*"


def _backup_keys() -> list[Fernet]:
    """Return current then previous backup keys, supporting safe rotation."""
    raw_keys = os.environ.get("BACKUP_ENCRYPTION_KEYS", "").split(",")
    keys = [key.strip() for key in raw_keys if key.strip()]
    return [
        Fernet(base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest()))
        for key in keys
    ]


def _encrypt_backup(path: Path) -> Path:
    keys = _backup_keys()
    if not keys:
        return path
    encrypted = path.with_suffix(path.suffix + ".enc")
    encrypted.write_bytes(keys[0].encrypt(path.read_bytes()))
    path.unlink()
    return encrypted


@contextmanager
def _readable_backup(path: Path):
    if path.suffix != ".enc":
        yield path
        return
    payload = path.read_bytes()
    plaintext = None
    for key in _backup_keys():
        try:
            plaintext = key.decrypt(payload)
            break
        except InvalidToken:
            continue
    if plaintext is None:
        raise ValueError("Şifreli yedek mevcut BACKUP_ENCRYPTION_KEYS ile açılamadı.")
    fd, name = tempfile.mkstemp(prefix="makro-backup-decrypt-", suffix=".db")
    os.close(fd)
    temporary = Path(name)
    try:
        temporary.write_bytes(plaintext)
        yield temporary
    finally:
        temporary.unlink(missing_ok=True)


def _db_path() -> Path:
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        return PROJECT_ROOT / "data" / "makroortodonti.db"
    if db_url == "sqlite:///:memory:":
        raise ValueError("Bellek içi SQLite veritabanı yedeklenemez.")
    if not db_url.startswith("sqlite:///"):
        raise ValueError("Bu araç yalnızca SQLite DATABASE_URL değerlerini destekler.")

    raw_path = unquote(db_url[len("sqlite:///") :].split("?", 1)[0])
    path = Path(raw_path)
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def _backup_dir() -> Path:
    return _db_path().parent / "backups"


def _integrity_result(path: Path) -> str:
    with closing(sqlite3.connect(str(path))) as conn:
        row = conn.execute("PRAGMA integrity_check").fetchone()
    return str(row[0]) if row else "no result"


def _online_backup(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(str(source))) as source_conn:
        with closing(sqlite3.connect(str(destination))) as destination_conn:
            source_conn.backup(destination_conn)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("değer 1 veya daha büyük olmalıdır")
    return parsed


def cmd_backup(args: argparse.Namespace) -> int:
    try:
        db_path = _db_path()
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not db_path.is_file():
        print(f"ERROR: Database not found at {db_path}", file=sys.stderr)
        return 1

    backup_dir = _backup_dir()
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S-%f")
    destination = backup_dir / f"makroortodonti_{timestamp}.db"
    try:
        _online_backup(db_path, destination)
        result = _integrity_result(destination)
        if result != "ok":
            raise sqlite3.DatabaseError(f"integrity_check: {result}")
        destination = _encrypt_backup(destination)
    except Exception as exc:
        destination.unlink(missing_ok=True)
        print(f"ERROR: Backup failed: {exc}", file=sys.stderr)
        return 1

    print(f"Backup created: {destination} ({destination.stat().st_size:,} bytes)")
    backups = sorted(backup_dir.glob(BACKUP_PATTERN))
    for old in backups[: -args.keep]:
        old.unlink()
        print(f"Removed old backup: {old.name}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    try:
        if args.file:
            target = Path(args.file).expanduser().resolve()
        else:
            backups = sorted(_backup_dir().glob(BACKUP_PATTERN))
            if not backups:
                print("No backups found.", file=sys.stderr)
                return 1
            target = backups[-1]
        if not target.is_file():
            print(f"ERROR: Backup file not found: {target}", file=sys.stderr)
            return 1
        with _readable_backup(target) as readable:
            result = _integrity_result(readable)
    except (ValueError, sqlite3.Error, OSError) as exc:
        print(f"ERROR: Verification failed: {exc}", file=sys.stderr)
        return 1

    print(f"Verifying: {target}")
    if result == "ok":
        print("Integrity check PASSED.")
        return 0
    print(f"Integrity check FAILED: {result}", file=sys.stderr)
    return 1


def cmd_list(_args: argparse.Namespace) -> int:
    try:
        backups = sorted(_backup_dir().glob(BACKUP_PATTERN))
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not backups:
        print("No backups found.")
        return 0
    for backup in backups:
        print(f"  {backup.name}  ({backup.stat().st_size / 1024:.1f} KB)")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    if not args.yes:
        print(
            "ERROR: Restore uygulamayı kapatıp --yes onayıyla çalıştırılmalıdır.",
            file=sys.stderr,
        )
        return 2

    source = Path(args.file).expanduser().resolve()
    if not source.is_file():
        print(f"ERROR: Backup file not found: {source}", file=sys.stderr)
        return 1
    try:
        db_path = _db_path()
    except (ValueError, sqlite3.Error, OSError) as exc:
        print(f"ERROR: Restore preflight failed: {exc}", file=sys.stderr)
        return 1

    if source == db_path.resolve():
        print("ERROR: Backup source and active database are the same file.", file=sys.stderr)
        return 1

    db_path.parent.mkdir(parents=True, exist_ok=True)
    original_mode = db_path.stat().st_mode if db_path.exists() else None

    if db_path.exists():
        safety = db_path.parent / (
            f"{db_path.stem}.pre-restore-"
            f"{datetime.now().strftime('%Y%m%dT%H%M%S%f')}.db"
        )
        try:
            _online_backup(db_path, safety)
            if _integrity_result(safety) != "ok":
                raise sqlite3.DatabaseError("safety backup integrity check failed")
        except Exception as exc:
            safety.unlink(missing_ok=True)
            print(f"ERROR: Safety backup failed; restore aborted: {exc}", file=sys.stderr)
            return 1
        print(f"Current database saved to: {safety}")

    temp_fd, temp_name = tempfile.mkstemp(
        prefix=f".{db_path.name}.restore-", suffix=".db", dir=db_path.parent
    )
    os.close(temp_fd)
    temporary = Path(temp_name)
    try:
        with _readable_backup(source) as readable:
            if _integrity_result(readable) != "ok":
                raise sqlite3.DatabaseError("source backup failed integrity check")
            _online_backup(readable, temporary)
        if _integrity_result(temporary) != "ok":
            raise sqlite3.DatabaseError("restored database integrity check failed")
        if original_mode is not None:
            os.chmod(temporary, original_mode)
        os.replace(temporary, db_path)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        print(f"ERROR: Restore failed: {exc}", file=sys.stderr)
        return 1

    print(f"Database restored atomically from: {source}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Makro Ortodonti database backup tool")
    subparsers = parser.add_subparsers(dest="command")

    backup_parser = subparsers.add_parser("backup", help="Create a verified backup")
    backup_parser.add_argument(
        "--keep", type=_positive_int, default=30, help="Backups to retain (default: 30)"
    )

    verify_parser = subparsers.add_parser("verify", help="Verify a backup")
    verify_parser.add_argument("file", nargs="?", help="Default: most recent backup")

    subparsers.add_parser("list", help="List available backups")

    restore_parser = subparsers.add_parser("restore", help="Restore a verified backup")
    restore_parser.add_argument("file", help="Path to the backup file")
    restore_parser.add_argument(
        "--yes", action="store_true", help="Confirm the destructive restore operation"
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    dispatch = {
        "backup": cmd_backup,
        "verify": cmd_verify,
        "list": cmd_list,
        "restore": cmd_restore,
    }
    if args.command not in dispatch:
        parser.print_help()
        raise SystemExit(0)
    raise SystemExit(dispatch[args.command](args))


if __name__ == "__main__":
    main()
