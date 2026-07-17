"""Database initialization and migration utilities."""

from __future__ import annotations

import os
import secrets
from datetime import date

import bcrypt
from sqlalchemy import text
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
    """Create tables using Flask-SQLAlchemy's engine (must be called inside app context)."""
    from flask import current_app
    from app.extensions import db

    os.makedirs(DATABASE_DIR, exist_ok=True)
    with current_app.app_context():
        Base.metadata.create_all(bind=db.engine)
        _create_indexes(db.engine)


def _create_indexes(engine) -> None:
    with engine.begin() as conn:
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_patients_name ON patients(last_name, first_name)",
            "CREATE INDEX IF NOT EXISTS idx_patient_treatments_date ON patient_treatments(treatment_date)",
            "CREATE INDEX IF NOT EXISTS idx_invoices_patient ON invoices(patient_id, invoice_date)",
            "CREATE INDEX IF NOT EXISTS idx_invoices_status_date ON invoices(status, invoice_date)",
            "CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice ON invoice_items(invoice_id)",
            "CREATE INDEX IF NOT EXISTS idx_treatments_category ON treatments(category, is_active)",
            "CREATE INDEX IF NOT EXISTS idx_exchange_rates_date ON exchange_rates(rate_date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(key)",
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
            "CREATE INDEX IF NOT EXISTS idx_whatsapp_status ON whatsapp_sessions(status)",
            "CREATE INDEX IF NOT EXISTS idx_parties_type ON parties(party_type)",
            "CREATE INDEX IF NOT EXISTS idx_parties_name ON parties(name)",
            "CREATE INDEX IF NOT EXISTS idx_parties_active ON parties(is_active)",
            "CREATE INDEX IF NOT EXISTS idx_invoices_party ON invoices(party_id, invoice_date)",
            "CREATE INDEX IF NOT EXISTS idx_invoice_items_type ON invoice_items(item_type)",
            "CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id)",
            "CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date)",
        ]
        for stmt in indexes:
            conn.execute(text(stmt))


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
    if env_password:
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
        Treatment(name="Metal Braces (Full Set)", description="Geleneksel metal braketler - tüm dişler", category=TreatmentCategory.ORTHODONTIC, price_eur=2500.00),
        Treatment(name="Ceramic Braces (Full Set)", description="Seramik braketler - görünmez tedavi", category=TreatmentCategory.ORTHODONTIC, price_eur=3200.00),
        Treatment(name="Lingual Braces", description="Dil tarafı braketler", category=TreatmentCategory.ORTHODONTIC, price_eur=4500.00),
        Treatment(name="Invisalign Full", description="Tam Invisalign tedavisi", category=TreatmentCategory.ORTHODONTIC, price_eur=4000.00),
        Treatment(name="Invisalign Lite", description="Kısa süreli Invisalign tedavisi", category=TreatmentCategory.ORTHODONTIC, price_eur=2800.00),
        Treatment(name="Invisalign Teen", description="Ergenler için Invisalign", category=TreatmentCategory.ORTHODONTIC, price_eur=3500.00),
        Treatment(name="Retainer (Hawley)", description="Hawley retainer - üst ve alt", category=TreatmentCategory.ORTHODONTIC, price_eur=250.00),
        Treatment(name="Retainer (Fixed)", description="Sabit retainer - tel Retansiyon", category=TreatmentCategory.ORTHODONTIC, price_eur=350.00),
        Treatment(name="Palatal Expander", description="Damak genişletici", category=TreatmentCategory.ORTHODONTIC, price_eur=600.00),
        Treatment(name="Headgear", description="Kafa aleti", category=TreatmentCategory.ORTHODONTIC, price_eur=400.00),
        Treatment(name="Elastic Rubber Bands", description="Kauçuk bantlar - aylık", category=TreatmentCategory.ORTHODONTIC, price_eur=30.00),
        Treatment(name="Orthodontic Adjustment", description="Braket ayarlama - kontrol", category=TreatmentCategory.ORTHODONTIC, price_eur=80.00),
        Treatment(name="Bracket Re-bonding", description="Braket yeniden yapıştırma", category=TreatmentCategory.ORTHODONTIC, price_eur=50.00),
        Treatment(name="Archwire Replacement", description="Tel değiştirme", category=TreatmentCategory.ORTHODONTIC, price_eur=60.00),
        Treatment(name="Porcelain Crown", description="Seramik kuron", category=TreatmentCategory.PROSTHETIC, price_eur=450.00),
        Treatment(name="Zirconia Crown", description="Zirkonyum kuron", category=TreatmentCategory.PROSTHETIC, price_eur=550.00),
        Treatment(name="PFM Crown", description="Metal destekli seramik kuron", category=TreatmentCategory.PROSTHETIC, price_eur=350.00),
        Treatment(name="Porcelain Veneer", description="Seramik lamina", category=TreatmentCategory.PROSTHETIC, price_eur=500.00),
        Treatment(name="Composite Veneer", description="Kompozit lamina", category=TreatmentCategory.PROSTHETIC, price_eur=250.00),
        Treatment(name="Removable Partial Denture", description="Hareketli protez", category=TreatmentCategory.PROSTHETIC, price_eur=800.00),
        Treatment(name="Full Denture (Upper)", description="Tam protez - üst çene", category=TreatmentCategory.PROSTHETIC, price_eur=1200.00),
        Treatment(name="Full Denture (Lower)", description="Tam protez - alt çene", category=TreatmentCategory.PROSTHETIC, price_eur=1200.00),
        Treatment(name="Dental Bridge (3-unit)", description="3 unitelik köprü", category=TreatmentCategory.PROSTHETIC, price_eur=1500.00),
        Treatment(name="Implant-Supported Bridge", description="İmplant destekli köprü - unit başına", category=TreatmentCategory.PROSTHETIC, price_eur=1800.00),
        Treatment(name="Simple Tooth Extraction", description="Basit diş çekimi", category=TreatmentCategory.SURGICAL, price_eur=150.00),
        Treatment(name="Surgical Extraction", description="Cerrahi diş çekimi", category=TreatmentCategory.SURGICAL, price_eur=350.00),
        Treatment(name="Wisdom Tooth Extraction", description="Yirmilik diş çekimi", category=TreatmentCategory.SURGICAL, price_eur=400.00),
        Treatment(name="Bone Graft", description="Kemik grefti", category=TreatmentCategory.SURGICAL, price_eur=600.00),
        Treatment(name="Sinus Lift", description="Sinüs kaldırma", category=TreatmentCategory.SURGICAL, price_eur=1200.00),
        Treatment(name="Gingivectomy", description="Diş eti düzeltme", category=TreatmentCategory.SURGICAL, price_eur=300.00),
        Treatment(name="Frenectomy", description="Frenulum düzeltme", category=TreatmentCategory.SURGICAL, price_eur=250.00),
        Treatment(name="Dental Implant (Titanium)", description="Titanyum implant - cerrahi", category=TreatmentCategory.IMPLANT, price_eur=1200.00),
        Treatment(name="Dental Implant (Premium)", description="Premium implant - cerrahi", category=TreatmentCategory.IMPLANT, price_eur=1800.00),
        Treatment(name="Implant Abutment", description="İmplant abutment", category=TreatmentCategory.IMPLANT, price_eur=300.00),
        Treatment(name="Implant Crown", description="İmplant üstü kuron", category=TreatmentCategory.IMPLANT, price_eur=500.00),
        Treatment(name="All-on-4 (Per Jaw)", description="All-on-4 tam çene implant", category=TreatmentCategory.IMPLANT, price_eur=8000.00),
        Treatment(name="Dental Cleaning (Prophylaxis)", description="Diş temizliği - prophylaxis", category=TreatmentCategory.PREVENTIVE, price_eur=100.00),
        Treatment(name="Fluoride Treatment", description="Flor uygulaması", category=TreatmentCategory.PREVENTIVE, price_eur=40.00),
        Treatment(name="Dental Sealant (Per Tooth)", description="Diş contası", category=TreatmentCategory.PREVENTIVE, price_eur=50.00),
        Treatment(name="Mouth Guard (Night)", description="Gece koruyucu", category=TreatmentCategory.PREVENTIVE, price_eur=200.00),
        Treatment(name="Mouth Guard (Sports)", description="Sporcu koruyucu", category=TreatmentCategory.PREVENTIVE, price_eur=150.00),
        Treatment(name="Composite Filling (Small)", description="Kompozit dolgu - küçük", category=TreatmentCategory.RESTORATIVE, price_eur=80.00),
        Treatment(name="Composite Filling (Medium)", description="Kompozit dolgu - orta", category=TreatmentCategory.RESTORATIVE, price_eur=120.00),
        Treatment(name="Composite Filling (Large)", description="Kompozit dolgu - büyük", category=TreatmentCategory.RESTORATIVE, price_eur=160.00),
        Treatment(name="Amalgam Filling", description="Amalgam dolgu", category=TreatmentCategory.RESTORATIVE, price_eur=70.00),
        Treatment(name="Inlay/Onlay", description="Inlay/Onlay restorasyon", category=TreatmentCategory.RESTORATIVE, price_eur=400.00),
        Treatment(name="Scaling & Root Planing", description="Küretaj ve köpekleşme", category=TreatmentCategory.ENDODONTIC, price_eur=300.00),
        Treatment(name="Periodontal Maintenance", description="Periodontal bakım", category=TreatmentCategory.ENDODONTIC, price_eur=150.00),
        Treatment(name="Root Canal (Anterior)", description="Kanal tedavisi - ön diş", category=TreatmentCategory.ENDODONTIC, price_eur=400.00),
        Treatment(name="Root Canal (Premolar)", description="Kanal tedavisi - premolar", category=TreatmentCategory.ENDODONTIC, price_eur=500.00),
        Treatment(name="Root Canal (Molar)", description="Kanal tedavisi - molar", category=TreatmentCategory.ENDODONTIC, price_eur=600.00),
        Treatment(name="Teeth Whitening (In-Office)", description="Profesyonel diş beyazlatma", category=TreatmentCategory.COSMETIC, price_eur=400.00),
        Treatment(name="Teeth Whitening (Take-Home)", description="Ev tipi beyazlatma kiti", category=TreatmentCategory.COSMETIC, price_eur=200.00),
        Treatment(name="Dental Bonding", description="Kompozit bonding", category=TreatmentCategory.COSMETIC, price_eur=200.00),
        Treatment(name="Consultation", description="Muayene ve danışmanlık", category=TreatmentCategory.OTHER, price_eur=50.00),
        Treatment(name="Panoramic X-Ray", description="Panoramik röntgen", category=TreatmentCategory.OTHER, price_eur=60.00),
        Treatment(name="Cephalometric X-Ray", description="Sefalometrik röntgen", category=TreatmentCategory.OTHER, price_eur=80.00),
        Treatment(name="CBCT Scan", description="3D tomografi", category=TreatmentCategory.OTHER, price_eur=200.00),
        Treatment(name="Emergency Visit", description="Acil durum ziyareti", category=TreatmentCategory.OTHER, price_eur=100.00),
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
        Party(party_type=PartyType.PATIENT, name="Ayşe Yılmaz", first_name="Ayşe", last_name="Yılmaz", phone="+905321112233", email="ayse@example.com", address="İstanbul, Kadıköy", treatment_status="active"),
        Party(party_type=PartyType.PATIENT, name="Mehmet Kaya", first_name="Mehmet", last_name="Kaya", phone="+905332223344", email="mehmet@example.com", address="İstanbul, Beşiktaş", treatment_status="active"),
        Party(party_type=PartyType.DENTIST_CUSTOMER, name="Dr. Elif Demir", first_name="Elif", last_name="Demir", phone="+905343334455", email="elif.demir@dentalclinic.com", address="İstanbul, Şişli"),
        Party(party_type=PartyType.DENTIST_CUSTOMER, name="Dr. Ahmet Özkan", first_name="Ahmet", last_name="Özkan", phone="+905354445566", email="ahmet.ozkan@smiledental.com", address="Ankara, Çankaya"),
        Party(party_type=PartyType.COMPANY_CUSTOMER, name="DentalPlus Laboratuvar", contact_person="Fatma Arslan", contact_phone="+905365556677", phone="+905365556677", email="info@dentalplus.com", address="İstanbul, Başakşehir"),
        Party(party_type=PartyType.COMPANY_CUSTOMER, name="SmileTech Malzeme", contact_person="Ali Çelik", contact_phone="+905376667788", phone="+905376667788", email="satis@smiletech.com", address="İzmir, Bornova"),
    ]
    db.session.add_all(sample_parties)
    db.session.commit()

    if is_generated:
        generated_password = admin_password
    return generated_password
