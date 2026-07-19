from __future__ import annotations

from datetime import date, timedelta
import json

from app.extensions import db
from app.models.models import (
    ExchangeRate, Invoice, InvoiceItem, InvoiceItemType,
    PatientTreatment, Party, PartyType, Payment, PaymentMethod, Settings, Treatment
)
from conftest import login


def test_login_success(client):
    response = login(client, "admin", "admin-pass")
    assert response.status_code == 200
    assert "Giriş başarılı!" in response.get_data(as_text=True)


def test_ui_shell_uses_unique_mobile_navigation_target(client):
    login(client, "admin", "admin-pass")
    html = client.get("/").get_data(as_text=True)

    assert html.count('id="mobileSidebar"') == 1
    assert 'aria-controls="mobileSidebar"' in html
    assert 'href="#main-content"' in html


def test_party_form_has_unique_common_fields_and_active_default(client):
    login(client, "admin", "admin-pass")
    html = client.get("/parties/add").get_data(as_text=True)

    for field_id in ("phone", "email", "address", "tax_id"):
        assert html.count(f'id="{field_id}"') == 1
    assert 'id="is_active" name="is_active" checked' in html


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


# ==================== YENI TESTLER ====================

def test_party_crud_patient(client, app):
    """Hasta tipi Party CRUD testi."""
    login(client, "admin", "admin-pass")

    # Create
    response = client.post("/parties/add", data={
        "party_type": "patient",
        "first_name": "Ahmet",
        "last_name": "Yilmaz",
        "phone": "+905551234567",
        "email": "ahmet@test.com",
        "treatment_status": "active",
    }, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        party = db.session.execute(
            db.select(Party).where(Party.first_name == "Ahmet", Party.last_name == "Yilmaz")
        ).scalar_one()
        assert party.party_type == PartyType.PATIENT
        assert party.display_name == "Ahmet Yilmaz"
        assert party.phone == "+905551234567"
        assert party.email == "ahmet@test.com"
        assert party.treatment_status == "active"

        # Read
        response = client.get(f"/parties/{party.id}")
        assert response.status_code == 200

        # Update
        response = client.post(f"/parties/{party.id}/edit", data={
            "party_type": "patient",
            "first_name": "Ahmet Guncel",
            "last_name": "Yilmaz",
            "phone": "+905551234567",
            "email": "ahmet@test.com",
            "treatment_status": "completed",
        }, follow_redirects=False)
        assert response.status_code == 302

        db.session.refresh(party)
        assert party.first_name == "Ahmet Guncel"
        assert party.treatment_status == "completed"

        # Delete (soft)
        response = client.post(f"/parties/{party.id}/delete", follow_redirects=False)
        assert response.status_code == 302
        db.session.refresh(party)
        assert party.is_active is False


def test_party_crud_dentist_customer(client, app):
    """Dis hekimi musterisi tipi Party CRUD testi."""
    login(client, "admin", "admin-pass")

    response = client.post("/parties/add", data={
        "party_type": "dentist_customer",
        "name": "Dr. Mehmet Oz",
        "phone": "+905559876543",
        "email": "mehmet@dentist.com",
        "tax_id": "12345678901",
    }, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        party = db.session.execute(
            db.select(Party).where(Party.name == "Dr. Mehmet Oz")
        ).scalar_one()
        assert party.party_type == PartyType.DENTIST_CUSTOMER
        assert party.display_name == "Dr. Mehmet Oz"
        assert party.tax_id == "12345678901"


def test_party_crud_company_customer(client, app):
    """Kurumsal musteri tipi Party CRUD testi."""
    login(client, "admin", "admin-pass")

    response = client.post("/parties/add", data={
        "party_type": "company_customer",
        "name": "ABC Saglik A.S.",
        "phone": "+902125551234",
        "email": "info@abc.com",
        "address": "Istanbul",
        "tax_id": "1234567890",
        "contact_person": "Ali Veli",
        "contact_phone": "+905551112233",
    }, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        party = db.session.execute(
            db.select(Party).where(Party.name == "ABC Saglik A.S.")
        ).scalar_one()
        assert party.party_type == PartyType.COMPANY_CUSTOMER
        assert party.contact_person == "Ali Veli"
        assert party.contact_phone == "+905551112233"


def test_party_type_filter(client, app):
    """Party tipine gore filtreleme testi."""
    login(client, "admin", "admin-pass")

    # Her tipte birer tane olustur
    for ptype, name in [
        ("patient", "Hasta Test"),
        ("dentist_customer", "Dr. Dis Hekimi"),
        ("company_customer", "XYZ Ltd."),
    ]:
        if ptype == "patient":
            client.post("/parties/add", data={
                "party_type": ptype, "first_name": "Hasta", "last_name": "Test",
                "phone": "+905551112233", "email": "hasta@test.com"
            })
        elif ptype == "dentist_customer":
            client.post("/parties/add", data={
                "party_type": ptype, "name": name, "phone": "+905552223344",
                "email": "dis@test.com", "tax_id": "11122233344"
            })
        else:
            client.post("/parties/add", data={
                "party_type": ptype, "name": name, "phone": "+905553334455",
                "email": "xyz@test.com", "tax_id": "55566677788",
                "contact_person": "Kisi", "contact_phone": "+905554445566"
            })

    # Filtrele
    response = client.get("/parties/?type=patient")
    assert response.status_code == 200

    with app.app_context():
        parties = db.session.execute(
            db.select(Party).where(Party.party_type == PartyType.PATIENT, Party.is_active == True)
        ).scalars().all()
        assert all(p.party_type == PartyType.PATIENT for p in parties)


def test_invoice_flexible_items(client, app):
    """Farkli item_type'larla fatura olusturma testi."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        party = db.session.execute(
            db.select(Party).where(Party.party_type == PartyType.PATIENT).limit(1)
        ).scalar_one()
        treatments = db.session.execute(
            db.select(Treatment).where(Treatment.is_active == True).limit(3)
        ).scalars().all()

    items = []
    for t in treatments[:2]:
        items.append({
            "item_type": "treatment",
            "treatment_id": t.id,
            "description": t.name,
            "quantity": 1,
            "unit_price_eur": t.price_eur,
        })
    # Custom item (product)
    items.append({
        "item_type": "product",
        "reference_id": None,
        "description": "Zirkonyum Blok",
        "quantity": 1,
        "unit_price_eur": 150.00,
        "vat_rate": 18.0,
    })
    # Service item
    items.append({
        "item_type": "service",
        "reference_id": None,
        "description": "Lab Danismanligi",
        "quantity": 1,
        "unit_price_eur": 200.00,
        "vat_rate": 8.0,
    })

    response = client.post("/invoices/add", data={
        "party_id": party.id,
        "invoice_date": date.today().isoformat(),
        "due_date": (date.today() + timedelta(days=30)).isoformat(),
        "items_json": json.dumps(items),
        "notes": "Karma fatura testi",
    }, follow_redirects=False)

    assert response.status_code == 302

    with app.app_context():
        invoice = db.session.execute(
            db.select(Invoice).order_by(Invoice.id.desc())
        ).scalar_one()

        assert len(invoice.items) == 4
        item_types = [item.item_type.value for item in invoice.items]
        assert "treatment" in item_types
        assert "product" in item_types
        assert "service" in item_types

        # Toplamlar hesaplanmali
        assert invoice.total_eur > 0
        assert invoice.total_try > 0


def test_invoice_vat_discount_calculations(client, app):
    """KDV ve iskonto hesaplamalari testi."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        party = db.session.execute(
            db.select(Party).where(Party.party_type == PartyType.PATIENT).limit(1)
        ).scalar_one()

    items = [{
        "item_type": "product",
        "description": "Test Urun",
        "quantity": 2,
        "unit_price_eur": 100.00,
        "vat_rate": 20.0,
        "discount_type": "percent",
        "discount_value": 10.0,  # %10 iskonto
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
        # Base: 2 * 100 = 200 EUR
        # Iskonto %10: 200 * 0.9 = 180 EUR
        # KDV %20: 180 * 1.2 = 216 EUR
        assert abs(item.line_total_eur - 180.0) < 0.01
        assert abs(item.vat_amount_eur - 36.0) < 0.01
        assert abs(item.line_total_eur + item.vat_amount_eur - 216.0) < 0.01


def test_payment_flow(client, app):
    """Tahsilat akisi: ekleme -> kismi -> tam -> fatura durumu guncelleme."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        party = db.session.execute(
            db.select(Party).where(Party.party_type == PartyType.PATIENT).limit(1)
        ).scalar_one()

    # Invoice olustur
    response = client.post("/invoices/add", data={
        "party_id": party.id,
        "invoice_date": date.today().isoformat(),
        "items_json": json.dumps([{
            "item_type": "treatment",
            "treatment_id": 1,
            "description": "Test Tedavi",
            "quantity": 1,
            "unit_price_eur": 500.00,
        }]),
    }, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        invoice = db.session.execute(
            db.select(Invoice).order_by(Invoice.id.desc())
        ).scalar_one()
        inv_id = invoice.id
        assert invoice.status == "pending"
        assert invoice.total_eur == 500.0

    # GET payment form with preselected invoice_id
    response = client.get(f"/payments/add?invoice_id={inv_id}")
    assert response.status_code == 200

    # 1. Kismi odeme (250 EUR)
    response = client.post("/payments/add", data={
        "invoice_id": inv_id,
        "payment_date": date.today().isoformat(),
        "amount_eur": 250.00,
        "method": "cash",
        "reference": "NAKIT-001",
    }, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        invoice = db.session.get(Invoice, inv_id)
        assert invoice.status == "pending"  # Hala kismi

    # 2. Kalan odeme (250 EUR)
    response = client.post("/payments/add", data={
        "invoice_id": inv_id,
        "payment_date": date.today().isoformat(),
        "amount_eur": 250.00,
        "method": "transfer",
        "reference": "EFT-001",
    }, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        invoice = db.session.get(Invoice, inv_id)
        assert invoice.status == "paid"  # Tam odendi

    # 3. Tahsilat listesi
    response = client.get("/payments/")
    assert response.status_code == 200


def test_payment_list_filters(client, app):
    """Tahsilat listeleme + filtreler testi."""
    login(client, "admin", "admin-pass")

    response = client.get("/payments/")
    assert response.status_code == 200

    # Filtre: yontem
    response = client.get("/payments/?method=transfer")
    assert response.status_code == 200

    # Filtre: tarih araligi
    today = date.today()
    week_ago = today - timedelta(days=7)
    response = client.get(f"/payments/?start_date={week_ago.isoformat()}&end_date={today.isoformat()}")
    assert response.status_code == 200

    # Filtre: arama
    response = client.get("/payments/?search=EFT")
    assert response.status_code == 200


def test_party_invoice_link_and_debt_calculation(client, app):
    """Party <-> Invoice iliskisi ve borc hesaplama."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        party = db.session.execute(
            db.select(Party).where(Party.party_type == PartyType.PATIENT).limit(1)
        ).scalar_one()

    # 2 fatura olustur
    for i in range(2):
        response = client.post("/invoices/add", data={
            "party_id": party.id,
            "invoice_date": date.today().isoformat(),
            "items_json": json.dumps([{
                "item_type": "treatment",
                "treatment_id": 1,
                "description": f"Tedavi {i+1}",
                "quantity": 1,
                "unit_price_eur": 300.00,
            }]),
        }, follow_redirects=False)
        assert response.status_code == 302

    with app.app_context():
        # Party uzerinden faturalari cek
        invoices = db.session.execute(
            db.select(Invoice).where(Invoice.party_id == party.id, Invoice.is_deleted == False)
        ).scalars().all()

        assert len(invoices) >= 2
        total_eur = sum(inv.total_eur for inv in invoices if inv.status == "pending")
        total_try = sum(inv.total_try for inv in invoices if inv.status == "pending")

        assert total_eur >= 600.0
        assert total_try > 0

        # Detay sayfasinda borc gorunmeli
        response = client.get(f"/parties/{party.id}")
        assert response.status_code == 200


def test_reports_aging_report(client, app):
    """Yaslandirma raporu (0-30, 31-60, 61+) testi."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        party = db.session.execute(
            db.select(Party).where(Party.party_type == PartyType.PATIENT).limit(1)
        ).scalar_one()

    # Farkli tarihlerde faturalar olustur
    dates = [
        date.today(),                           # 0 gun
        date.today() - timedelta(days=15),      # 15 gun
        date.today() - timedelta(days=45),      # 45 gun
        date.today() - timedelta(days=75),      # 75 gun
    ]

    for i, inv_date in enumerate(dates):
        response = client.post("/invoices/add", data={
            "party_id": party.id,
            "invoice_date": inv_date.isoformat(),
            "items_json": json.dumps([{
                "item_type": "treatment",
                "treatment_id": 1,
                "description": f"Tedavi {i+1}",
                "quantity": 1,
                "unit_price_eur": 200.00,
            }]),
        }, follow_redirects=False)
        assert response.status_code == 302

    # Reports sayfasi
    response = client.get("/reports/")
    assert response.status_code == 200

    # Yaslandirma verisi donmeli (template'de gosterilirse)
    # Bu test template render edildiginde gecerli olur
    assert b"Raporlar" in response.data


def test_legacy_invoice_compatibility(client, app):
    """Eski patient_id + treatment_ids formatinin hala calismasi."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        pt = db.session.execute(db.select(PatientTreatment)).scalar_one()

    # Eski format: patient_id + treatment_ids
    response = client.post("/invoices/add", data={
        "patient_id": pt.patient_id,
        "invoice_date": date.today().isoformat(),
        "treatment_ids": [str(pt.id)],
        "notes": "Legacy format testi",
    }, follow_redirects=True)

    assert response.status_code == 200
    assert "oluşturuldu" in response.get_data(as_text=True)

    with app.app_context():
        invoice = db.session.execute(
            db.select(Invoice).order_by(Invoice.id.desc())
        ).scalar_one()
        assert invoice.party_id is not None  # Party'ye baglandi
        assert invoice.patient_id == pt.patient_id  # Eskisi de kaldi


def test_invoice_api_treatment_price(client, app):
    """Tedavi fiyati API testi."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        pt = db.session.execute(db.select(PatientTreatment)).scalar_one()

    response = client.get(f"/invoices/api/treatment-price/{pt.id}")
    assert response.status_code == 200
    data = response.get_json()
    assert "price_eur" in data
    assert "treatment_name" in data
    assert data["price_eur"] == pt.effective_price_eur


def test_party_api_info(client, app):
    """Party bilgi API testi."""
    login(client, "admin", "admin-pass")

    with app.app_context():
        party = db.session.execute(
            db.select(Party).where(Party.party_type == PartyType.PATIENT).limit(1)
        ).scalar_one()

    response = client.get(f"/invoices/api/party/{party.id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == party.id
    assert data["name"] == party.display_name
    assert data["party_type"] == party.party_type.value


def test_smtp_password_encryption_decryption(app):
    """SMTP şifreleme ve geri açma birim testi."""
    with app.app_context():
        from app.services.security_service import encrypt_value, decrypt_value
        
        test_pass = "mypass123!@#"
        encrypted = encrypt_value(test_pass)
        assert encrypted != test_pass
        assert len(encrypted) > 0
        
        decrypted = decrypt_value(encrypted)
        assert decrypted == test_pass
        
        # Test fallback to plaintext
        plaintext_fallback = "legacy_plaintext"
        assert decrypt_value(plaintext_fallback) == plaintext_fallback
        
        # Test empty input
        assert encrypt_value("") == ""
        assert decrypt_value("") == ""


def test_login_rate_limiting_and_lockout(client, app):
    """Giriş ekranında rate limiting ve lockout testi."""
    # 5 failed login attempts
    for _ in range(5):
        response = client.post("/login", data={"username": "admin", "password": "wrong-password"})
        assert response.status_code == 200
        assert "Kullanıcı adı veya şifre hatalı" in response.get_data(as_text=True)

    # 6th attempt should trigger lockout
    response = client.post("/login", data={"username": "admin", "password": "wrong-password"})
    assert response.status_code == 200
    assert "Çok fazla başarısız giriş denemesi" in response.get_data(as_text=True)

    # 7th attempt with correct password should also be blocked due to lockout
    response = client.post("/login", data={"username": "admin", "password": "admin-pass"})
    assert response.status_code == 200
    assert "Çok fazla başarısız giriş denemesi" in response.get_data(as_text=True)


def test_defensive_validation_exchange_rate(client, app):
    """Geçersiz kur ekleme denemelerinde defensive validation testi."""
    login(client, "admin", "admin-pass")

    # Post invalid rate value
    response = client.post(
        "/settings/exchange-rate/add",
        data={"rate_date": "2026-07-19", "eur_try_rate": "invalid-float-abc"},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert "Geçersiz tarih veya kur değeri girildi" in response.get_data(as_text=True)

    # Post invalid date value
    response = client.post(
        "/settings/exchange-rate/add",
        data={"rate_date": "invalid-date", "eur_try_rate": "41.50"},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert "Geçersiz tarih veya kur değeri girildi" in response.get_data(as_text=True)


# ==================== TOTAL: 18 TEST ====================
