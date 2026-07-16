from __future__ import annotations

from datetime import date

from app.extensions import db
from app.models.models import ExchangeRate, Invoice, PatientTreatment, Settings
from conftest import login


def test_login_success(client):
    response = login(client, "admin", "admin-pass")
    assert response.status_code == 200
    assert "Giriş başarılı!" in response.get_data(as_text=True)


def test_invoice_create_flow(client, app):
    login(client, "admin", "admin-pass")

    with app.app_context():
        patient_treatment = db.session.execute(db.select(PatientTreatment)).scalar_one()

    response = client.post(
        "/invoices/add",
        data={
            "patient_id": patient_treatment.patient_id,
            "invoice_date": date.today().isoformat(),
            "treatment_ids": [str(patient_treatment.id)],
            "notes": "Test fatura",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "oluşturuldu" in response.get_data(as_text=True)

    with app.app_context():
        created = db.session.execute(db.select(Invoice)).scalars().all()
        assert len(created) == 1
        assert created[0].total_eur > 0
        assert created[0].total_try > 0


def test_settings_update_does_not_overwrite_unsent_fields(client, app):
    login(client, "admin", "admin-pass")

    response = client.post(
        "/settings/update",
        data={
            "clinic_name": "Yeni Klinik",
            "clinic_phone": "02120000000",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        smtp_user = db.session.execute(
            db.select(Settings.value).where(Settings.key == "smtp_username")
        ).scalar_one_or_none()
        clinic_name = db.session.execute(
            db.select(Settings.value).where(Settings.key == "clinic_name")
        ).scalar_one_or_none()

    assert smtp_user == "old-user@example.com"
    assert clinic_name == "Yeni Klinik"


def test_rate_fetch_updates_today_rate(client, app, monkeypatch):
    login(client, "admin", "admin-pass")

    def fake_fetch_rate():
        return 41.75

    monkeypatch.setattr("app.services.exchange_service.fetch_eur_try_rate", fake_fetch_rate)

    response = client.post("/settings/exchange-rate/fetch", follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        rate = db.session.execute(
            db.select(ExchangeRate).where(ExchangeRate.rate_date == date.today())
        ).scalar_one_or_none()

    assert rate is not None
    assert rate.eur_to_try == 41.75


def test_invoice_pdf_download_works(client, app):
    login(client, "admin", "admin-pass")

    with app.app_context():
        patient_treatment = db.session.execute(db.select(PatientTreatment)).scalar_one()

    client.post(
        "/invoices/add",
        data={
            "patient_id": patient_treatment.patient_id,
            "invoice_date": date.today().isoformat(),
            "treatment_ids": [str(patient_treatment.id)],
            "notes": "PDF test",
        },
        follow_redirects=True,
    )

    with app.app_context():
        invoice = db.session.execute(db.select(Invoice).limit(1)).scalar_one()

    response = client.get(f"/invoices/{invoice.id}/pdf")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
