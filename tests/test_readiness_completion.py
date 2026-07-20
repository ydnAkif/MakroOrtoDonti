from __future__ import annotations

import argparse
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import backup
from app.authz import has_permission
from app.models.base import Base
from app.models.invoice_service import InvoiceService
from app.models.models import Settings
from app.services.validation_service import normalize_treatment_fields
from deployment_check import validate_environment
from production_drill import create_drill


def test_invoice_counter_is_atomic_across_concurrent_transactions(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'counter.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([
            Settings(key="invoice_prefix", value="MKR"),
            Settings(key="invoice_next_number", value="1"),
        ])
        session.commit()

    barrier = threading.Barrier(2)

    def issue_number():
        with Session(engine) as session:
            barrier.wait(timeout=5)
            number = InvoiceService.generate_invoice_number(session, date(2026, 7, 20))
            session.commit()
            return number

    with ThreadPoolExecutor(max_workers=2) as pool:
        numbers = sorted(pool.map(lambda _index: issue_number(), range(2)))

    assert numbers == ["MKR-2026-0001", "MKR-2026-0002"]
    with Session(engine) as session:
        counter = session.execute(
            select(Settings.value).where(Settings.key == "invoice_next_number")
        ).scalar_one()
    assert counter == "3"
    engine.dispose()


def test_invoice_counter_fails_closed_when_setting_missing(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'missing.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Settings(key="invoice_prefix", value="MKR"))
        session.commit()
        try:
            InvoiceService.generate_invoice_number(session)
        except RuntimeError as exc:
            assert "invoice_next_number" in str(exc)
        else:
            raise AssertionError("missing counter must fail closed")
    engine.dispose()


def test_treatment_validation_is_shared_and_strict():
    assert normalize_treatment_fields(" Muayene ", " Açıklama ", "diğer", "12,50") == (
        "Muayene", "Açıklama", "other", __import__("decimal").Decimal("12.50")
    )
    for values in [
        ("", None, "other", "1"),
        ("Test", None, "bilinmeyen", "1"),
        ("Test", None, "other", "nan"),
        ("Test", None, "other", "-1"),
    ]:
        try:
            normalize_treatment_fields(*values)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid treatment accepted: {values}")


def test_permission_matrix_separates_staff_duties():
    staff = type("User", (), {"role": "staff"})()
    admin = type("User", (), {"role": "admin"})()
    assert has_permission(staff, "clinical.edit")
    assert has_permission(staff, "billing.edit")
    assert has_permission(staff, "reports.view")
    assert not has_permission(staff, "billing.delete")
    assert not has_permission(staff, "settings.manage")
    assert not has_permission(staff, "privacy.export")
    assert has_permission(admin, "privacy.export")


def test_encrypted_backup_supports_key_rotation(tmp_path, monkeypatch):
    database = tmp_path / "active.db"
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE sample (value TEXT)")
        conn.execute("INSERT INTO sample VALUES ('secret')")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEYS", "current-key-that-is-longer-than-thirty-two-characters")

    assert backup.cmd_backup(argparse.Namespace(keep=2)) == 0
    encrypted = next((tmp_path / "backups").glob("*.db.enc"))
    assert b"secret" not in encrypted.read_bytes()
    assert backup.cmd_verify(argparse.Namespace(file=str(encrypted))) == 0

    monkeypatch.setenv(
        "BACKUP_ENCRYPTION_KEYS",
        "new-key-that-is-longer-than-thirty-two-characters,current-key-that-is-longer-than-thirty-two-characters",
    )
    assert backup.cmd_verify(argparse.Namespace(file=str(encrypted))) == 0


def test_deployment_preflight_is_fail_closed():
    good = {
        "SECRET_KEY": "session-secret-that-is-longer-than-thirty-two-characters",
        "ENCRYPTION_KEY": "settings-secret-that-is-longer-than-thirty-two-characters",
        "BACKUP_ENCRYPTION_KEYS": "backup-secret-that-is-longer-than-thirty-two-characters",
        "SESSION_COOKIE_SECURE": "true",
        "FORCE_HSTS": "true",
        "DATABASE_ENCRYPTION_AT_REST": "true",
        "REMOTE_BACKUP_URL": "s3://clinic-backups/makro",
        "TRUST_PROXY": "true",
        "FORWARDED_ALLOW_IPS": "10.0.0.10",
    }
    assert validate_environment(good) == []
    assert validate_environment({})
    assert validate_environment({**good, "FORWARDED_ALLOW_IPS": "*"})


def test_anonymized_production_drill_creates_verified_manifest(tmp_path):
    source = tmp_path / "production-copy.db"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE parties (id INTEGER PRIMARY KEY, name TEXT, first_name TEXT, last_name TEXT, phone TEXT, email TEXT, address TEXT, tax_id TEXT, notes TEXT, date_of_birth TEXT, contact_person TEXT, contact_phone TEXT)")
        conn.execute("INSERT INTO parties VALUES (1, 'Ayşe Yılmaz', 'Ayşe', 'Yılmaz', '555', 'a@example.com', 'Adres', '123', 'Not', '1990-01-01', NULL, NULL)")

    artifact, manifest_path = create_drill(source, tmp_path / "drill")
    manifest = json.loads(manifest_path.read_text())
    assert manifest["pii_anonymized"] is True
    assert manifest["integrity_check"] == "ok"
    with sqlite3.connect(artifact) as conn:
        row = conn.execute("SELECT name, phone, email FROM parties").fetchone()
    assert row == ("ANON-1", None, None)
