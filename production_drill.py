#!/usr/bin/env python3
"""Create and verify an anonymized SQLite migration/restore rehearsal artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


PII_UPDATES = {
    "parties": """
        UPDATE parties SET name='ANON-' || id, first_name='Anonim', last_name=CAST(id AS TEXT),
        phone=NULL, email=NULL, address=NULL, tax_id=NULL, notes=NULL,
        date_of_birth=NULL, contact_person=NULL, contact_phone=NULL
    """,
    "patients": """
        UPDATE patients SET first_name='Anonim', last_name=CAST(id AS TEXT), phone=NULL,
        email=NULL, address=NULL, notes=NULL, date_of_birth=NULL
    """,
    "users": "UPDATE users SET username='drill-user-' || id, full_name='Test User ' || id, last_login=NULL",
    "settings": "UPDATE settings SET value='' WHERE key LIKE 'smtp_%' OR key LIKE 'clinic_%' OR key='tax_id'",
    "patient_treatments": "UPDATE patient_treatments SET notes=NULL",
    "invoices": "UPDATE invoices SET notes=NULL",
    "payments": "UPDATE payments SET reference=NULL, notes=NULL",
    "login_attempts": "UPDATE login_attempts SET ip_address='0.0.0.0', username='anonymous'",
    "audit_logs": "UPDATE audit_logs SET actor_username=NULL, ip_address=NULL, changes_json=NULL",
    "whatsapp_sessions": "UPDATE whatsapp_sessions SET phone_number=NULL, qr_code=NULL",
}


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def create_drill(source: Path, output_dir: Path) -> tuple[Path, Path]:
    if not source.is_file():
        raise ValueError(f"Kaynak veritabanı bulunamadı: {source}")
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact = output_dir / f"production-drill-{stamp}.db"

    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(artifact)) as dst:
        src.backup(dst)
        tables = _tables(dst)
        for table, statement in PII_UPDATES.items():
            if table in tables:
                dst.execute(statement)
        dst.commit()
        integrity = dst.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = dst.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or foreign_keys:
            raise RuntimeError(f"Tatbikat kopyası doğrulanamadı: integrity={integrity}, fk={foreign_keys[:5]}")

    # Simulate transfer to and restore on a second host with another SQLite file.
    restored = output_dir / f"production-drill-{stamp}-restored.db"
    with closing(sqlite3.connect(artifact)) as src, closing(sqlite3.connect(restored)) as dst:
        src.backup(dst)
        if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Restore tatbikatı integrity kontrolünden geçmedi")

    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = output_dir / f"production-drill-{stamp}.json"
    manifest.write_text(json.dumps({
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifact": artifact.name,
        "sha256": digest,
        "restored_copy": restored.name,
        "source_included": False,
        "pii_anonymized": True,
        "integrity_check": "ok",
        "foreign_key_check": "ok",
    }, ensure_ascii=False, indent=2) + "\n")
    return artifact, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    artifact, manifest = create_drill(args.database.resolve(), args.output_dir.resolve())
    print(f"Anonymized drill artifact: {artifact}")
    print(f"Manifest: {manifest}")


if __name__ == "__main__":
    main()
