"""Database initialization and migration utilities."""

from __future__ import annotations

import os
import secrets
from datetime import date

import bcrypt
from sqlalchemy.orm import Session

from .base import Base
from .models import (
    ExchangeRate,
    Invoice,
    InvoiceItem,
    Party,
    PartyType,
    Patient,
    PatientTreatment,
    Payment,
    Settings,
    Treatment,
    TreatmentCategory,
    User,
    WhatsAppSession,
)

# Project paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATABASE_DIR = os.path.join(PROJECT_ROOT, "data")
DATABASE_PATH = os.path.join(DATABASE_DIR, "makroortodonti.db")


def init_db() -> None:
    """Upgrade the configured database to the latest Alembic revision."""
    from flask_migrate import upgrade

    os.makedirs(DATABASE_DIR, exist_ok=True)
    upgrade()


def migrate_patients_to_parties() -> int:
    """Migrate existing patients to Party records. Must be called inside app context."""
    from app.extensions import db

    migrated = 0
    patients = db.session.execute(
        db.select(Patient).where(Patient.party_id.is_(None))
    ).scalars().all()

    for patient in patients:
        existing = db.session.execute(
            db.select(Party).where(
                Party.party_type == PartyType.PATIENT,
                Party.first_name == patient.first_name,
                Party.last_name == patient.last_name,
                Party.phone == patient.phone,
            )
        ).scalar_one_or_none()

        if existing:
            patient.party_id = existing.id
        else:
            party = Party(
                party_type=PartyType.PATIENT,
                name=f"{patient.first_name} {patient.last_name}",
                first_name=patient.first_name,
                last_name=patient.last_name,
                phone=patient.phone,
                email=patient.email,
                address=patient.address,
                tax_id=getattr(patient, 'tax_id', None),
                notes=patient.notes,
                date_of_birth=patient.date_of_birth,
                treatment_status=patient.treatment_status,
                is_active=patient.is_active,
            )
            db.session.add(party)
            db.session.flush()
            patient.party_id = party.id
        migrated += 1

    if migrated > 0:
        db.session.commit()

    return migrated


def link_invoices_to_parties() -> int:
    """Link existing invoices to parties via their patients. Must be called inside app context."""
    from app.extensions import db

    linked = 0
    invoices = db.session.execute(
        db.select(Invoice).where(Invoice.party_id.is_(None))
    ).scalars().all()

    for invoice in invoices:
        if invoice.patient and invoice.patient.party_id:
            invoice.party_id = invoice.patient.party_id
            linked += 1

    if linked > 0:
        db.session.commit()

    return linked


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _is_valid_bcrypt_hash(password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        bcrypt.checkpw(b"__probe__", password_hash.encode("utf-8"))
        return True
    except ValueError:
        return False


def _resolve_admin_password() -> tuple[str, bool]:
    env_password = os.environ.get("DEFAULT_ADMIN_PASSWORD", "").strip()
    is_debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    is_testing = os.environ.get("TESTING", "false").lower() == "true" or os.environ.get("PYTEST_CURRENT_TEST") is not None
    
    if env_password:
        if (
            (len(env_password) < 12 or env_password.lower() in ("admin123", "admin", "123456", "password"))
            and not is_debug
            and not is_testing
        ):
            # Reject weak password in production, generate a secure one-time password
            random_pw = secrets.token_urlsafe(12)
            print("\n[CRITICAL SECURITY WARNING] Weak DEFAULT_ADMIN_PASSWORD rejected in production!")
            print(f"Generating a random secure one-time password instead: {random_pw}\n")
            return random_pw, True
        return env_password, False
    return secrets.token_urlsafe(12), True


def seed_sample_data() -> str | None:
    """Seed sample data using Flask-SQLAlchemy session. Must be called inside app context."""
    from app.extensions import db

    generated_password: str | None = None
    has_seed_data = db.session.execute(
        db.select(Treatment).limit(1)
    ).scalar_one_or_none() is not None

    if has_seed_data:
        admin_user = db.session.execute(
            db.select(User).where(User.username == "admin")
        ).scalar_one_or_none()

        if admin_user is None:
            admin_password, is_generated = _resolve_admin_password()
            db.session.add(
                User(
                    username="admin",
                    password_hash=_hash_password(admin_password),
                    full_name="Admin",
                    role=User.ROLE_ADMIN,
                )
            )
            db.session.commit()
            if is_generated:
                generated_password = admin_password
            return generated_password

        if not _is_valid_bcrypt_hash(admin_user.password_hash):
            admin_password, is_generated = _resolve_admin_password()
            admin_user.password_hash = _hash_password(admin_password)
            db.session.commit()
            if is_generated:
                generated_password = admin_password
        return generated_password

    treatments = [
        Treatment(name="Dijital Planlama (Tek Çene)", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1750.00, currency="TL"),
        Treatment(name="Lingual Ark", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1000.00, currency="TL"),
        Treatment(name="Dijital Plak (Adet)", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1200.00, currency="TL"),
        Treatment(name="Nance", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1100.00, currency="TL"),
        Treatment(name="Şeffaf Plak (Soft, Medium, Hard)", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1600.00, currency="TL"),
        Treatment(name="TPA", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1000.00, currency="TL"),
        Treatment(name="Set-up'lı Sx", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1100.00, currency="TL"),
        Treatment(name="Habit Appliances", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1200.00, currency="TL"),
        Treatment(name="Dijital Model (Adet)", category=TreatmentCategory.ANA_ISLEMLER, price_eur=500.00, currency="TL"),
        Treatment(name="Quad Helix", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1200.00, currency="TL"),
        Treatment(name="Bi Helix", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1200.00, currency="TL"),
        Treatment(name="Lingual Indirect Bonding Tek Çene 7-7", category=TreatmentCategory.ANA_ISLEMLER, price_eur=3500.00, currency="TL"),
        Treatment(name="Lingual Indirect Bonding set-upsız Tek Diş", category=TreatmentCategory.ANA_ISLEMLER, price_eur=300.00, currency="TL"),
        Treatment(name="Rapid Expansion (Hyrax Type) (Vidasız)", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1400.00, currency="TL"),
        Treatment(name="Labial Indirect Bonding Tek Çene", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1600.00, currency="TL"),
        Treatment(name="Rapid Expansion (Mc Namara) (Vidasız)", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1500.00, currency="TL"),
        Treatment(name="Rapid Expansion (Fan Type) (Vidasız)", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1500.00, currency="TL"),
        Treatment(name="Hawley", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1100.00, currency="TL"),
        Treatment(name="Molar Slider", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1500.00, currency="TL"),
        Treatment(name="Wrap Around", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1100.00, currency="TL"),
        Treatment(name="Pendulum Appliance", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1500.00, currency="TL"),
        Treatment(name="Lingual Retainer", category=TreatmentCategory.ANA_ISLEMLER, price_eur=450.00, currency="TL"),
        Treatment(name="Expansion (Transverse)", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1500.00, currency="TL"),
        Treatment(name="Sx Plak", category=TreatmentCategory.ANA_ISLEMLER, price_eur=375.00, currency="TL"),
        Treatment(name="Expansion (3 way Type) (Vidasız)", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1400.00, currency="TL"),
        Treatment(name="Yer Tutucu (Sabit)", category=TreatmentCategory.ANA_ISLEMLER, price_eur=850.00, currency="TL"),
        Treatment(name="Expansion (Fan Type) (Vidasız)", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1400.00, currency="TL"),
        Treatment(name="Yer Tutucu (Hareketli)", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1100.00, currency="TL"),
        Treatment(name="Bite Plate", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1500.00, currency="TL"),
        Treatment(name="Gece Plağı", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1000.00, currency="TL"),
        Treatment(name="Activator (FKO)", category=TreatmentCategory.ANA_ISLEMLER, price_eur=2500.00, currency="TL"),
        Treatment(name="Durasoft Gece Plağı (2.5 mm)", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1600.00, currency="TL"),
        Treatment(name="Bionator (Açık-Kapalı)", category=TreatmentCategory.ANA_ISLEMLER, price_eur=2700.00, currency="TL"),
        Treatment(name="Eklem Splinti", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1750.00, currency="TL"),
        Treatment(name="Frankel (I, II, III, IV)", category=TreatmentCategory.ANA_ISLEMLER, price_eur=3000.00, currency="TL"),
        Treatment(name="Twin Block", category=TreatmentCategory.ANA_ISLEMLER, price_eur=3300.00, currency="TL"),
        Treatment(name="Horlama Apareyi (Akrilik)", category=TreatmentCategory.ANA_ISLEMLER, price_eur=2900.00, currency="TL"),
        Treatment(name="Herbst", category=TreatmentCategory.ANA_ISLEMLER, price_eur=4000.00, currency="TL"),
        Treatment(name="Horlama Apareyi (Plak)", category=TreatmentCategory.ANA_ISLEMLER, price_eur=3600.00, currency="TL"),
        Treatment(name="Horlama Apareyi (SomnoMed)", category=TreatmentCategory.ANA_ISLEMLER, price_eur=5000.00, currency="TL"),
        Treatment(name="Hotz Plate", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1100.00, currency="TL"),
        Treatment(name="Beyazlatma Plağı", category=TreatmentCategory.ANA_ISLEMLER, price_eur=1100.00, currency="TL"),
        Treatment(name="Sporcu Plağı", category=TreatmentCategory.ANA_ISLEMLER, price_eur=2800.00, currency="TL"),
        Treatment(name="PRO Sporcu Plağı", category=TreatmentCategory.ANA_ISLEMLER, price_eur=4000.00, currency="TL"),
        Treatment(name="Bant", category=TreatmentCategory.EKSTRA_ISLEMLER, price_eur=3.00, currency="USD"),
        Treatment(name="Activator Tüpü", category=TreatmentCategory.EKSTRA_ISLEMLER, price_eur=5.00, currency="EUR"),
        Treatment(name="Tüplü Bant", category=TreatmentCategory.EKSTRA_ISLEMLER, price_eur=4.00, currency="USD"),
        Treatment(name="Hyrax Vida", category=TreatmentCategory.EKSTRA_ISLEMLER, price_eur=20.00, currency="EUR"),
        Treatment(name="Lingual Sheat", category=TreatmentCategory.EKSTRA_ISLEMLER, price_eur=4.00, currency="USD"),
        Treatment(name="3 way (Bertoni)", category=TreatmentCategory.EKSTRA_ISLEMLER, price_eur=25.00, currency="EUR"),
        Treatment(name="Ekstra Vida", category=TreatmentCategory.EKSTRA_ISLEMLER, price_eur=4.50, currency="EUR"),
        Treatment(name="Fantype (Hyrax)", category=TreatmentCategory.EKSTRA_ISLEMLER, price_eur=60.00, currency="EUR"),
        Treatment(name="Z Zemberek, Finger Spring Vs.", category=TreatmentCategory.EKSTRA_ISLEMLER, price_eur=100.00, currency="TL"),
        Treatment(name="Oklüzyon Yükseltme", category=TreatmentCategory.EKSTRA_ISLEMLER, price_eur=100.00, currency="TL"),
    ]

    settings_defaults = Settings.DEFAULTS.copy()
    settings_defaults["invoice_next_number"] = "1"

    admin_password, is_generated = _resolve_admin_password()
    admin_user = User(
        username="admin",
        password_hash=_hash_password(admin_password),
        full_name="Admin",
        role=User.ROLE_ADMIN,
    )

    sample_rate = ExchangeRate(
        rate_date=date.today(),
        eur_to_try=37.50,
        source="ecb",
    )

    db.session.add_all(treatments)

    existing_settings = {
        s.key for s in db.session.execute(db.select(Settings)).scalars().all()
    }
    new_settings = [
        Settings(key=k, value=v) for k, v in settings_defaults.items() if k not in existing_settings
    ]
    if new_settings:
        db.session.add_all(new_settings)

    db.session.add(admin_user)

    existing_rate = db.session.execute(
        db.select(ExchangeRate).where(
            ExchangeRate.rate_date == date.today(),
            ExchangeRate.source == "ecb",
        )
    ).scalar_one_or_none()
    if not existing_rate:
        db.session.add(sample_rate)

    sample_parties = [
        Party(party_type=PartyType.DENTIST, name="Dr. Elif Demir", phone="+905343334455", email="elif.demir@dentalclinic.com", address="İstanbul, Şişli"),
        Party(party_type=PartyType.DENTIST, name="Dr. Ahmet Özkan", phone="+905354445566", email="ahmet.ozkan@smiledental.com", address="Ankara, Çankaya"),
        Party(party_type=PartyType.DENTIST, name="Dr. Fatma Arslan", phone="+905365556677", email="fatma.arslan@dentplus.com", address="İstanbul, Başakşehir"),
        Party(party_type=PartyType.DENTIST, name="Dr. Ali Çelik", phone="+905376667788", email="ali.celik@smiledental.com", address="İzmir, Bornova"),
    ]
    db.session.add_all(sample_parties)
    db.session.commit()

    if is_generated:
        generated_password = admin_password
    return generated_password
