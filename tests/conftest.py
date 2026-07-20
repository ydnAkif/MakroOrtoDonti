from __future__ import annotations

from datetime import date
from decimal import Decimal
import threading

import bcrypt
import pytest
from werkzeug.serving import make_server

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
            "clinic_name": "Makro Ortodonti",
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
                party_id=party.id,
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

    with app.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, username: str, password: str):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


@pytest.fixture(scope="session")
def live_server_url(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("e2e") / "makro.db"

    class E2EConfig:
        TESTING = True
        DEBUG = False
        SECRET_KEY = "e2e-session-key-longer-than-thirty-two-characters"
        ENCRYPTION_KEY = "e2e-encryption-key-longer-than-thirty-two-characters"
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        WTF_CSRF_ENABLED = True
        SESSION_COOKIE_SECURE = False
        TRUST_PROXY = False
        FORCE_HSTS = False
        MAX_CONTENT_LENGTH = 16 * 1024 * 1024
        AUDIT_RETENTION_DAYS = 3650

    e2e_app = create_app(E2EConfig)
    with e2e_app.app_context():
        Base.metadata.create_all(bind=db.engine)
        db.session.add(User(
            username="admin", full_name="E2E Admin", role="admin",
            password_hash=bcrypt.hashpw(b"admin-pass", bcrypt.gensalt()).decode(),
        ))
        db.session.add(Party(
            party_type=PartyType.PATIENT, name="E2E Hasta", first_name="E2E",
            last_name="Hasta", phone="5551112233",
        ))
        db.session.add(Treatment(name="E2E Muayene", category="other", price_eur=Decimal("50.00")))
        db.session.add(ExchangeRate(rate_date=date.today(), eur_to_try=Decimal("40.0000"), source="ecb"))
        db.session.add(Settings(key="invoice_prefix", value="MKR"))
        db.session.add(Settings(key="invoice_next_number", value="1"))
        db.session.commit()

    server = make_server("127.0.0.1", 0, e2e_app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=5)
    with e2e_app.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def authenticated_page(page, live_server_url):
    page.goto(f"{live_server_url}/login")
    page.get_by_label("Kullanıcı Adı").fill("admin")
    page.get_by_label("Şifre").fill("admin-pass")
    page.get_by_role("button", name="Giriş Yap").click()
    page.wait_for_url(f"{live_server_url}/")
    return page
