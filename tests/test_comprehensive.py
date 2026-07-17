"""Comprehensive tests covering all major application flows."""

from __future__ import annotations

from datetime import date, timedelta
import io
import json

from app.extensions import db
from app.models.models import (
    ExchangeRate, Invoice, InvoiceItem, InvoiceItemType,
    Patient, PatientTreatment, Party, PartyType, Payment, PaymentMethod,
    Settings, Treatment, User
)
from conftest import login


# ==================== AUTH ====================

def test_login_invalid_password(client):
    """Yanlis sifre ile giris yapilamaz."""
    response = client.post("/login", data={"username": "admin", "password": "wrong"})
    assert response.status_code == 200
    assert "Kullanıcı adı veya şifre hatalı" in response.get_data(as_text=True)


def test_login_invalid_username(client):
    """Var olmayan kullanici ile giris yapilamaz."""
    response = client.post("/login", data={"username": "nonexistent", "password": "x"})
    assert response.status_code == 200
    assert "Kullanıcı adı veya şifre hatalı" in response.get_data(as_text=True)


def test_logout(client):
    """Cikis yapilabilmeli."""
    login(client, "admin", "admin-pass")
    response = client.get("/logout", follow_redirects=True)
    assert response.status_code == 200


def test_unauthenticated_redirect(client):
    """Giris yapilmamis istekler login sayfasina yonlendirilmeli."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.location


# ==================== DASHBOARD ====================

def test_dashboard_loads(client, app):
    """Dashboard sayfasi acilmali ve temel bilgileri gostermeli."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        party = db.session.execute(
            db.select(Party).where(Party.party_type == PartyType.PATIENT).limit(1)
        ).scalar_one()
        client.post("/invoices/add", data={
            "party_id": party.id,
            "invoice_date": date.today().isoformat(),
            "items_json": json.dumps([{
                "item_type": "treatment",
                "treatment_id": 1,
                "description": "Dashboard Test",
                "quantity": 1,
                "unit_price_eur": 100.00,
            }]),
        })

    response = client.get("/")
    assert response.status_code == 200
    assert "Makro" in response.get_data(as_text=True)


# ==================== PATIENTS CRUD ====================

def test_patient_list(client, app):
    """Hasta listesi gorunmeli."""
    login(client, "admin", "admin-pass")
    response = client.get("/patients/")
    assert response.status_code == 200


def test_patient_add(client, app):
    """Hasta ekleme + otomatik Party olusturma."""
    login(client, "admin", "admin-pass")

    response = client.post("/patients/add", data={
        "first_name": "Zeynep",
        "last_name": "Kaya",
        "phone": "5559998877",
        "email": "zeynep@test.com",
        "treatment_status": "active",
    }, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        patient = db.session.execute(
            db.select(Patient).where(Patient.first_name == "Zeynep", Patient.last_name == "Kaya")
        ).scalar_one()
        assert patient.phone == "5559998877"
        assert patient.party_id is not None
        party = db.session.get(Party, patient.party_id)
        assert party is not None
        assert party.party_type == PartyType.PATIENT


def test_patient_detail(client, app):
    """Hasta detay sayfasi acilmali."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        patient_id = db.session.execute(db.select(Patient).limit(1)).scalar_one().id

    response = client.get(f"/patients/{patient_id}")
    assert response.status_code == 200


def test_patient_edit(client, app):
    """Hasta guncelleme + Party senkronizasyonu."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        patient_id = db.session.execute(db.select(Patient).limit(1)).scalar_one().id

    response = client.post(f"/patients/{patient_id}/edit", data={
        "first_name": "Guncellenmis",
        "last_name": "Hasta",
        "phone": "5550001122",
        "email": "updated@test.com",
        "treatment_status": "completed",
    }, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        patient = db.session.get(Patient, patient_id)
        assert patient.first_name == "Guncellenmis"
        assert patient.treatment_status == "completed"
        party = db.session.get(Party, patient.party_id)
        assert party.first_name == "Guncellenmis"


def test_patient_delete(client, app):
    """Hasta soft-delete + Party deaktivasyonu."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        patient_id = db.session.execute(db.select(Patient).limit(1)).scalar_one().id

    response = client.post(f"/patients/{patient_id}/delete", follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        patient = db.session.get(Patient, patient_id)
        assert patient.is_active is False
        if patient.party_id:
            party = db.session.get(Party, patient.party_id)
            assert party.is_active is False


def test_patient_add_treatment(client, app):
    """Hastaya tedavi ekleme."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        patient_id = db.session.execute(db.select(Patient).limit(1)).scalar_one().id
        treatment_id = db.session.execute(
            db.select(Treatment).where(Treatment.name == "Crown")
        ).scalar_one().id

    response = client.post(f"/patients/{patient_id}/add-treatment", data={
        "treatment_id": treatment_id,
        "treatment_date": date.today().isoformat(),
        "price_override": "",
        "notes": "Test tedavi",
    }, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        count = db.session.execute(
            db.select(PatientTreatment).where(
                PatientTreatment.patient_id == patient_id,
                PatientTreatment.treatment_id == treatment_id,
            )
        ).scalars().all()
        assert len(count) >= 1


# ==================== TREATMENTS CRUD ====================

def test_treatment_list(client, app):
    """Tedavi listesi gorunmeli."""
    login(client, "admin", "admin-pass")
    response = client.get("/treatments/")
    assert response.status_code == 200
    assert "Consultation" in response.get_data(as_text=True)


def test_treatment_list_filter_category(client, app):
    """Tedavi listesi kategoriye gore filtrelenmeli."""
    login(client, "admin", "admin-pass")
    response = client.get("/treatments/?category=prosthetic")
    assert response.status_code == 200
    assert "Crown" in response.get_data(as_text=True)


def test_treatment_list_search(client, app):
    """Tedavi listesi arama ile filtrelenmeli."""
    login(client, "admin", "admin-pass")
    response = client.get("/treatments/?search=Crown")
    assert response.status_code == 200


def test_treatment_add(client, app):
    """Tedavi ekleme (admin)."""
    login(client, "admin", "admin-pass")

    response = client.post("/treatments/add", data={
        "name": "New Treatment",
        "description": "A new test treatment",
        "category": "orthodontic",
        "price_eur": 150.00,
    }, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        t = db.session.execute(
            db.select(Treatment).where(Treatment.name == "New Treatment")
        ).scalar_one()
        assert t.category == "orthodontic"
        assert t.price_eur == 150.00


def test_treatment_edit(client, app):
    """Tedavi guncelleme (admin)."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        treatment_id = db.session.execute(
            db.select(Treatment).where(Treatment.name == "Consultation")
        ).scalar_one().id

    response = client.post(f"/treatments/{treatment_id}/edit", data={
        "name": "Consultation Updated",
        "description": "Updated desc",
        "category": "other",
        "price_eur": 75.00,
    }, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        t = db.session.get(Treatment, treatment_id)
        assert t.name == "Consultation Updated"
        assert t.price_eur == 75.00


def test_treatment_delete(client, app):
    """Tedavi soft-delete (admin)."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        treatment_id = db.session.execute(
            db.select(Treatment).where(Treatment.name == "Extraction")
        ).scalar_one().id

    response = client.post(f"/treatments/{treatment_id}/delete", follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        t = db.session.get(Treatment, treatment_id)
        assert t.is_active is False


def test_treatment_api_update(client, app):
    """Tedavi inline guncelleme API'si."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        treatment_id = db.session.execute(
            db.select(Treatment).where(Treatment.name == "Crown")
        ).scalar_one().id

    response = client.post("/treatments/api/update",
        data=json.dumps({"id": treatment_id, "name": "Crown Updated", "price_eur": 250.00}),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["treatment"]["name"] == "Crown Updated"
    assert data["treatment"]["price_eur"] == 250.00


def test_treatment_api_update_invalid_id(client, app):
    """Var olmayan tedavi guncellenemez."""
    login(client, "admin", "admin-pass")

    response = client.post("/treatments/api/update",
        data=json.dumps({"id": 99999, "name": "X"}),
        content_type="application/json",
    )
    assert response.status_code == 404


def test_treatment_import_xlsx(client, app):
    """XLSX dosyasindan tedavi ice aktarma."""
    login(client, "admin", "admin-pass")

    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["Tedavi Adi", "Kategori", "Fiyat (EUR)", "Aciklama"])
    ws.append(["Imported Treatment 1", "ortodonti", 120.0, "Imported desc 1"])
    ws.append(["Imported Treatment 2", "cerrahi", 300.0, "Imported desc 2"])
    ws.append(["Consultation", "diger", 55.0, "Updated via import"])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    response = client.post("/treatments/import",
        data={"file": (buf, "test.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        t1 = db.session.execute(
            db.select(Treatment).where(Treatment.name == "Imported Treatment 1")
        ).scalar_one_or_none()
        assert t1 is not None
        assert t1.price_eur == 120.0
        assert t1.category == "orthodontic"

        t2 = db.session.execute(
            db.select(Treatment).where(Treatment.name == "Imported Treatment 2")
        ).scalar_one_or_none()
        assert t2 is not None

        consult = db.session.execute(
            db.select(Treatment).where(Treatment.name == "Consultation")
        ).scalar_one()
        assert consult.price_eur == 55.0


def test_treatment_import_invalid_file(client, app):
    """Gecersiz dosya turu reddedilmeli."""
    login(client, "admin", "admin-pass")

    response = client.post("/treatments/import",
        data={"file": (io.BytesIO(b"test"), "test.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "desteklenir" in response.get_data(as_text=True)


# ==================== INVOICES ====================

def test_invoice_list(client, app):
    """Fatura listesi gorunmeli."""
    login(client, "admin", "admin-pass")

    response = client.get("/invoices/")
    assert response.status_code == 200


def test_invoice_list_filter_by_status(client, app):
    """Fatura listesi duruma gore filtrelenmeli."""
    login(client, "admin", "admin-pass")

    response = client.get("/invoices/?status=pending")
    assert response.status_code == 200

    response = client.get("/invoices/?status=paid")
    assert response.status_code == 200


def test_invoice_detail(client, app):
    """Fatura detay sayfasi acilmali."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        party = db.session.execute(
            db.select(Party).where(Party.party_type == PartyType.PATIENT).limit(1)
        ).scalar_one()
        client.post("/invoices/add", data={
            "party_id": party.id,
            "invoice_date": date.today().isoformat(),
            "items_json": json.dumps([{
                "item_type": "treatment",
                "treatment_id": 1,
                "description": "Detail Test",
                "quantity": 1,
                "unit_price_eur": 200.00,
            }]),
        })
        invoice_id = db.session.execute(
            db.select(Invoice).order_by(Invoice.id.desc())
        ).scalar_one().id

    response = client.get(f"/invoices/{invoice_id}")
    assert response.status_code == 200


def test_invoice_status_update(client, app):
    """Fatura durumu guncellenebilmeli."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        party = db.session.execute(
            db.select(Party).where(Party.party_type == PartyType.PATIENT).limit(1)
        ).scalar_one()
        client.post("/invoices/add", data={
            "party_id": party.id,
            "invoice_date": date.today().isoformat(),
            "items_json": json.dumps([{
                "item_type": "treatment",
                "treatment_id": 1,
                "description": "Status Test",
                "quantity": 1,
                "unit_price_eur": 100.00,
            }]),
        })
        invoice_id = db.session.execute(
            db.select(Invoice).order_by(Invoice.id.desc())
        ).scalar_one().id

    response = client.post(f"/invoices/{invoice_id}/status", data={
        "status": "paid",
    }, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        invoice = db.session.get(Invoice, invoice_id)
        assert invoice.status == "paid"


def test_invoice_soft_delete(client, app):
    """Fatura soft-delete."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        party = db.session.execute(
            db.select(Party).where(Party.party_type == PartyType.PATIENT).limit(1)
        ).scalar_one()
        client.post("/invoices/add", data={
            "party_id": party.id,
            "invoice_date": date.today().isoformat(),
            "items_json": json.dumps([{
                "item_type": "treatment",
                "treatment_id": 1,
                "description": "Delete Test",
                "quantity": 1,
                "unit_price_eur": 100.00,
            }]),
        })
        invoice_id = db.session.execute(
            db.select(Invoice).order_by(Invoice.id.desc())
        ).scalar_one().id

    response = client.post(f"/invoices/{invoice_id}/delete", follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        invoice = db.session.get(Invoice, invoice_id)
        assert invoice.is_deleted is True


def test_invoice_with_party_preselect(client, app):
    """Party ID ile fatura olustururken otomatik secim."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        party_id = db.session.execute(
            db.select(Party).where(Party.party_type == PartyType.PATIENT).limit(1)
        ).scalar_one().id

    response = client.get(f"/invoices/add?party_id={party_id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert f'value="{party_id}"' in html


def test_invoice_no_items_rejected(client, app):
    """Kalemsiz fatura olusturulamamali."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        party_id = db.session.execute(
            db.select(Party).where(Party.party_type == PartyType.PATIENT).limit(1)
        ).scalar_one().id

    response = client.post("/invoices/add", data={
        "party_id": party_id,
        "invoice_date": date.today().isoformat(),
        "notes": "Kalemsiz test",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "En az bir kalem" in response.get_data(as_text=True)


def test_invoice_amount_discount(client, app):
    """Tutar bazli iskonto hesaplamasi."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        party = db.session.execute(
            db.select(Party).where(Party.party_type == PartyType.PATIENT).limit(1)
        ).scalar_one()

    items = [{
        "item_type": "service",
        "description": "Lab Hizmeti",
        "quantity": 1,
        "unit_price_eur": 300.00,
        "discount_type": "amount",
        "discount_value": 50.00,
    }]

    response = client.post("/invoices/add", data={
        "party_id": party.id,
        "invoice_date": date.today().isoformat(),
        "items_json": json.dumps(items),
    }, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        invoice = db.session.execute(
            db.select(Invoice).order_by(Invoice.id.desc())
        ).scalar_one()
        item = invoice.items[0]
        assert abs(item.line_total_eur - 250.0) < 0.01


def test_invoice_search(client, app):
    """Fatura numarasi ile arama."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        party = db.session.execute(
            db.select(Party).where(Party.party_type == PartyType.PATIENT).limit(1)
        ).scalar_one()
        client.post("/invoices/add", data={
            "party_id": party.id,
            "invoice_date": date.today().isoformat(),
            "items_json": json.dumps([{
                "item_type": "treatment",
                "treatment_id": 1,
                "description": "Search Test",
                "quantity": 1,
                "unit_price_eur": 100.00,
            }]),
        })
        inv_num = db.session.execute(
            db.select(Invoice).order_by(Invoice.id.desc())
        ).scalar_one().invoice_number

    response = client.get(f"/invoices/?search={inv_num}")
    assert response.status_code == 200


# ==================== PAYMENTS ====================

def test_payment_add(client, app):
    """Yeni tahsilat ekleme."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        party = db.session.execute(
            db.select(Party).where(Party.party_type == PartyType.PATIENT).limit(1)
        ).scalar_one()
        client.post("/invoices/add", data={
            "party_id": party.id,
            "invoice_date": date.today().isoformat(),
            "items_json": json.dumps([{
                "item_type": "treatment",
                "treatment_id": 1,
                "description": "Payment Add Test",
                "quantity": 1,
                "unit_price_eur": 300.00,
            }]),
        })
        invoice_id = db.session.execute(
            db.select(Invoice).order_by(Invoice.id.desc())
        ).scalar_one().id

    response = client.post("/payments/add", data={
        "invoice_id": invoice_id,
        "payment_date": date.today().isoformat(),
        "amount_eur": 100.00,
        "method": "transfer",
        "reference": "TEST-REF-001",
    }, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        payment = db.session.execute(
            db.select(Payment).where(Payment.invoice_id == invoice_id)
        ).scalar_one()
        assert payment.amount_eur == 100.0
        assert payment.method == PaymentMethod.TRANSFER


def test_payment_delete(client, app):
    """Tahsilat silme + fatura durumu geri alma."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        party = db.session.execute(
            db.select(Party).where(Party.party_type == PartyType.PATIENT).limit(1)
        ).scalar_one()
        client.post("/invoices/add", data={
            "party_id": party.id,
            "invoice_date": date.today().isoformat(),
            "items_json": json.dumps([{
                "item_type": "treatment",
                "treatment_id": 1,
                "description": "Payment Delete Test",
                "quantity": 1,
                "unit_price_eur": 500.00,
            }]),
        })
        invoice_id = db.session.execute(
            db.select(Invoice).order_by(Invoice.id.desc())
        ).scalar_one().id

    # Full payment
    response = client.post("/payments/add", data={
        "invoice_id": invoice_id,
        "payment_date": date.today().isoformat(),
        "amount_eur": 500.00,
        "method": "cash",
    }, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        invoice = db.session.get(Invoice, invoice_id)
        assert invoice.status == "paid"
        payment_id = db.session.execute(
            db.select(Payment).where(Payment.invoice_id == invoice_id)
        ).scalar_one().id

    # Delete payment
    response = client.post(f"/payments/{payment_id}/delete", follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        invoice = db.session.get(Invoice, invoice_id)
        assert invoice.status == "pending"


# ==================== SETTINGS ====================

def test_settings_page_loads(client, app):
    """Ayarlar sayfasi acilmali."""
    login(client, "admin", "admin-pass")
    response = client.get("/settings/")
    assert response.status_code == 200


def test_settings_update_clinic_info(client, app):
    """Klinik bilgileri guncellenebilmeli."""
    login(client, "admin", "admin-pass")

    response = client.post("/settings/update", data={
        "clinic_name": "Guncellenmis Klinik",
        "clinic_phone": "02121112233",
        "clinic_email": "info@klinik.com",
        "clinic_address": "Ankara",
    }, follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        name = db.session.execute(
            db.select(Settings.value).where(Settings.key == "clinic_name")
        ).scalar_one()
        assert name == "Guncellenmis Klinik"


def test_exchange_rate_add_manual(client, app):
    """Manuel kur ekleme."""
    login(client, "admin", "admin-pass")

    response = client.post("/settings/exchange-rate/add", data={
        "rate_date": "2025-01-15",
        "eur_try_rate": "38.5000",
    }, follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        rate = db.session.execute(
            db.select(ExchangeRate).where(ExchangeRate.rate_date == date(2025, 1, 15))
        ).scalar_one_or_none()
        assert rate is not None
        assert rate.eur_to_try == 38.5


# ==================== REPORTS ====================

def test_reports_page_loads(client, app):
    """Raporlar sayfasi acilmali."""
    login(client, "admin", "admin-pass")
    response = client.get("/reports/")
    assert response.status_code == 200
    assert "Raporlar" in response.get_data(as_text=True)


# ==================== PARTY SEARCH ====================

def test_party_search(client, app):
    """Kisi arama calismali."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        party = db.session.execute(
            db.select(Party).where(Party.party_type == PartyType.PATIENT).limit(1)
        ).scalar_one()

    response = client.get(f"/parties/?search={party.first_name}")
    assert response.status_code == 200


def test_party_referred_by(client, app):
    """Hasta sevk bilgisi (referred_by) kaydedilebilmeli."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        dentist = db.session.execute(
            db.select(Party).where(Party.party_type == PartyType.DENTIST_CUSTOMER).limit(1)
        ).scalar_one_or_none()
        if not dentist:
            client.post("/parties/add", data={
                "party_type": "dentist_customer",
                "name": "Dr. Sevk Hekimi",
                "phone": "5550000000",
            })
            dentist = db.session.execute(
                db.select(Party).where(Party.name == "Dr. Sevk Hekimi")
            ).scalar_one()

    response = client.post("/parties/add", data={
        "party_type": "patient",
        "first_name": "Sevkli",
        "last_name": "Hasta",
        "phone": "5551234567",
        "referred_by_id": dentist.id,
    }, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        party = db.session.execute(
            db.select(Party).where(Party.first_name == "Sevkli", Party.last_name == "Hasta")
        ).scalar_one()
        assert party.referred_by_id == dentist.id
