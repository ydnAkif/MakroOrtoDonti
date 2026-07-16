from __future__ import annotations

from datetime import date

import bcrypt
import pytest

from app import create_app
from app.extensions import db
from app.models.base import Base
from app.models.models import ExchangeRate, Patient, PatientTreatment, Settings, Treatment, User


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
        treatment = Treatment(name="Consultation", category="other", price_eur=50.0)
        db.session.add(patient)
        db.session.add(treatment)
        db.session.flush()

        db.session.add(
            PatientTreatment(
                patient_id=patient.id,
                treatment_id=treatment.id,
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
