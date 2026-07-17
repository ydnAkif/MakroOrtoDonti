from __future__ import annotations

from datetime import date

import bcrypt
import pytest

from app import create_app
from app.extensions import db
from app.models.base import Base
from app.models.models import (
    ExchangeRate, Patient, PatientTreatment, Party, PartyType, Settings, Treatment, User
)


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret"
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


@pytest.fixture()
def app():
    app = create_app(TestConfig)

    with app.app_context():
        Base.metadata.create_all(bind=db.engine)

        default_settings = {
            "clinic_name": "Makro Orto Denti",
            "invoice_prefix": "MKR",
            "invoice_next_number": "1",
            "smtp_server": "smtp.gmail.com",
            "smtp_port": "587",
            "smtp_username": "old-user@example.com",
            "smtp_password": "old-pass",
        }
        for key, value in default_settings.items():
            db.session.add(Settings(key=key, value=value))

        admin_hash = bcrypt.hashpw(b"admin-pass", bcrypt.gensalt()).decode("utf-8")
        staff_hash = bcrypt.hashpw(b"staff-pass", bcrypt.gensalt()).decode("utf-8")

        db.session.add(
            User(
                username="admin",
                password_hash=admin_hash,
                full_name="Admin User",
                role=User.ROLE_ADMIN,
            )
        )
        db.session.add(
            User(
                username="staff",
                password_hash=staff_hash,
                full_name="Staff User",
                role=User.ROLE_STAFF,
            )
        )

        patient = Patient(first_name="Ayse", last_name="Yilmaz", phone="5551112233")
        db.session.add(patient)
        db.session.flush()

        treatments_seed = [
            Treatment(name="Consultation", category="other", price_eur=50.0),
            Treatment(name="Crown", category="prosthetic", price_eur=200.0),
            Treatment(name="Extraction", category="surgical", price_eur=100.0),
        ]
        for t in treatments_seed:
            db.session.add(t)
        db.session.flush()

        # Create Party linked to Patient
        party = Party(
            party_type=PartyType.PATIENT,
            name=f"{patient.first_name} {patient.last_name}",
            first_name=patient.first_name,
            last_name=patient.last_name,
            phone=patient.phone,
            email=patient.email,
            address=patient.address,
            notes=patient.notes,
            date_of_birth=patient.date_of_birth,
            treatment_status=patient.treatment_status,
            is_active=patient.is_active,
        )
        db.session.add(party)
        db.session.flush()

        patient.party_id = party.id

        db.session.add(
            PatientTreatment(
                patient_id=patient.id,
                treatment_id=treatments_seed[0].id,
                treatment_date=date.today(),
                price_override_eur=55.0,
            )
        )

        db.session.add(
            ExchangeRate(rate_date=date.today(), eur_to_try=40.0, source="ecb")
        )
        db.session.commit()

    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, username: str, password: str):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )
