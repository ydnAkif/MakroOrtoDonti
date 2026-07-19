#!/usr/bin/env python3
"""
Backup and restore utilities for the Makro Ortodonti SQLite database.

Usage
-----
Back up the database (creates a timestamped copy in data/backups/):
    python backup.py backup

Verify the integrity of the most-recent backup:
    python backup.py verify

List available backups:
    python backup.py list

Restore from a specific backup file:
    python backup.py restore data/backups/makroortodonti_2025-01-01T12-00-00.db

All commands honour the DATABASE_URL environment variable; if it is not set the
default path data/makroortodonti.db is used.
"""

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def _db_path() -> Path:
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url.startswith("sqlite:///"):
        return Path(db_url[len("sqlite:///"):])
    # Default relative to this script
    return Path(__file__).parent / "data" / "makroortodonti.db"


def _backup_dir() -> Path:
    return _db_path().parent / "backups"


def cmd_backup(args) -> int:  # noqa: ANN001
    db_path = _db_path()
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}", file=sys.stderr)
        return 1

    backup_dir = _backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    dest = backup_dir / f"makroortodonti_{timestamp}.db"

    # Use SQLite online backup API for a consistent copy
    src_conn = sqlite3.connect(str(db_path))
    dst_conn = sqlite3.connect(str(dest))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    # Verify the backup immediately
    try:
        conn = sqlite3.connect(str(dest))
        result = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
        if result[0] != "ok":
            print(f"ERROR: Integrity check failed: {result[0]}", file=sys.stderr)
            dest.unlink(missing_ok=True)
            return 1
    except Exception as exc:
        print(f"ERROR: Could not verify backup: {exc}", file=sys.stderr)
        return 1

    print(f"Backup created: {dest} ({dest.stat().st_size:,} bytes)")

    # Keep only the most-recent N backups
    keep = getattr(args, "keep", 30)
    backups = sorted(backup_dir.glob("makroortodonti_*.db"))
    for old in backups[:-keep]:
        old.unlink()
        print(f"Removed old backup: {old.name}")

    return 0


def cmd_verify(args) -> int:  # noqa: ANN001
    backup_dir = _backup_dir()
    backups = sorted(backup_dir.glob("makroortodonti_*.db"))
    if not backups:
        print("No backups found.", file=sys.stderr)
        return 1

    target = backups[-1]
    print(f"Verifying: {target}")
    conn = sqlite3.connect(str(target))
    result = conn.execute("PRAGMA integrity_check").fetchone()
    conn.close()
    if result[0] == "ok":
        print("Integrity check PASSED.")
        return 0
    else:
        print(f"Integrity check FAILED: {result[0]}", file=sys.stderr)
        return 1


def cmd_list(args) -> int:  # noqa: ANN001
    backup_dir = _backup_dir()
    backups = sorted(backup_dir.glob("makroortodonti_*.db"))
    if not backups:
        print("No backups found.")
        return 0
    for b in backups:
        size_kb = b.stat().st_size / 1024
        print(f"  {b.name}  ({size_kb:.1f} KB)")
    return 0


def cmd_restore(args) -> int:  # noqa: ANN001
    src = Path(args.file)
    if not src.exists():
        print(f"ERROR: Backup file not found: {src}", file=sys.stderr)
        return 1

    # Verify source first
    conn = sqlite3.connect(str(src))
    result = conn.execute("PRAGMA integrity_check").fetchone()
    conn.close()
    if result[0] != "ok":
        print(f"ERROR: Source backup failed integrity check: {result[0]}", file=sys.stderr)
        return 1

    db_path = _db_path()

    # Create a safety backup of the current DB before overwriting
    if db_path.exists():
        safety = db_path.with_suffix(
            f".pre-restore-{datetime.now().strftime('%Y%m%dT%H%M%S')}.db"
        )
        shutil.copy2(db_path, safety)
        print(f"Current database saved to: {safety}")

    # Restore
    src_conn = sqlite3.connect(str(src))
    dst_conn = sqlite3.connect(str(db_path))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    print(f"Database restored from: {src}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Makro Ortodonti database backup tool")
    sub = parser.add_subparsers(dest="command")

    p_backup = sub.add_parser("backup", help="Create a timestamped backup")
    p_backup.add_argument("--keep", type=int, default=30, help="Number of backups to retain")

    sub.add_parser("verify", help="Verify the most-recent backup")
    sub.add_parser("list", help="List available backups")

    p_restore = sub.add_parser("restore", help="Restore database from a backup file")
    p_restore.add_argument("file", help="Path to the backup file")

    args = parser.parse_args()
    dispatch = {
        "backup": cmd_backup,
        "verify": cmd_verify,
        "list": cmd_list,
        "restore": cmd_restore,
    }

    if args.command not in dispatch:
        parser.print_help()
        sys.exit(0)

    sys.exit(dispatch[args.command](args))


if __name__ == "__main__":
    main()
