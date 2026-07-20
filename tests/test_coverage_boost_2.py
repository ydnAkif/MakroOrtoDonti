"""Massive coverage boost for routes and services still below target."""

import io
import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.extensions import db
from app.models.models import (
    ExchangeRate, Invoice, InvoiceItem, InvoiceItemType,
    LoginAttempt, Party, PartyType, Patient, PatientTreatment,
    Payment, PaymentMethod, Settings, Treatment, User,
)
from app.models.invoice_service import InvoiceService
from conftest import login


def _create_party(session, **kwargs):
    defaults = {"party_type": PartyType.DENTIST, "name": "Test Party", "is_active": True}
    defaults.update(kwargs)
    p = Party(**defaults)
    session.add(p)
    session.commit()
    return p


def _create_invoice(session, party_id, items=None, **kwargs):
    if items is None:
        items = [{"item_type": "service", "description": "Svc", "quantity": 1, "unit_price_eur": 100}]
    inv = InvoiceService.create_invoice(
        session=session, party_id=party_id, items=items,
        invoice_date=kwargs.get("invoice_date", date.today()),
        due_date=kwargs.get("due_date"),
        notes=kwargs.get("notes"),
    )
    return inv


# ============================================================
# health.py (40% → 100%)
# ============================================================

class TestHealth:
    def test_health_ok(self, client, app):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["db"] is True

    def test_health_degraded(self, client, app):
        with patch("app.routes.health.db") as mock_db:
            mock_db.session.execute.side_effect = Exception("DB down")
            response = client.get("/health")
            assert response.status_code == 503
            data = response.get_json()
            assert data["status"] == "degraded"
            assert data["db"] is False


# ============================================================
# payments.py (14% → 85%+)
# ============================================================

class TestPayments:
    def _get_invoice(self, app):
        with app.app_context():
            p = _create_party(db.session)
            inv = _create_invoice(db.session, p.id)
            return inv.id

    def test_list_payments(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/payments/")
        assert resp.status_code == 200

    def test_list_payments_with_search(self, client, app):
        inv_id = self._get_invoice(app)
        login(client, "admin", "admin-pass")
        resp = client.get("/payments/?search=MKR")
        assert resp.status_code == 200

    def test_list_payments_with_method_filter(self, client, app):
        inv_id = self._get_invoice(app)
        with app.app_context():
            inv = db.session.get(Invoice, inv_id)
            p = Payment(
                invoice_id=inv.id, payment_date=date.today(),
                amount_eur=50, amount_try=2000, exchange_rate=40,
                method=PaymentMethod.CASH, reference="REF1",
            )
            db.session.add(p)
            db.session.commit()
        login(client, "admin", "admin-pass")
        resp = client.get("/payments/?method=cash")
        assert resp.status_code == 200

    def test_list_payments_with_date_filter(self, client, app):
        inv_id = self._get_invoice(app)
        with app.app_context():
            inv = db.session.get(Invoice, inv_id)
            p = Payment(
                invoice_id=inv.id, payment_date=date.today(),
                amount_eur=50, amount_try=2000, exchange_rate=40,
                method=PaymentMethod.TRANSFER,
            )
            db.session.add(p)
            db.session.commit()
        login(client, "admin", "admin-pass")
        resp = client.get(f"/payments/?start_date={date.today().strftime('%d.%m.%Y')}&end_date={date.today().strftime('%d.%m.%Y')}")
        assert resp.status_code == 200

    def test_add_payment_get(self, client, app):
        inv_id = self._get_invoice(app)
        login(client, "admin", "admin-pass")
        resp = client.get(f"/payments/add?invoice_id={inv_id}")
        assert resp.status_code == 200

    def test_add_payment_get_no_invoice(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/payments/add")
        assert resp.status_code == 200

    def test_add_payment_success(self, client, app):
        inv_id = self._get_invoice(app)
        login(client, "admin", "admin-pass")
        resp = client.post("/payments/add", data={
            "invoice_id": inv_id,
            "payment_date": date.today().strftime("%d.%m.%Y"),
            "amount_eur": "50",
            "method": "cash",
            "reference": "TEST123",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_add_payment_missing_fields(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.post("/payments/add", data={
            "invoice_id": "",
            "amount_eur": "",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_add_payment_invalid_method(self, client, app):
        inv_id = self._get_invoice(app)
        login(client, "admin", "admin-pass")
        resp = client.post("/payments/add", data={
            "invoice_id": inv_id,
            "payment_date": date.today().strftime("%d.%m.%Y"),
            "amount_eur": "50",
            "method": "invalid_method",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_add_payment_no_exchange_rate(self, client, app):
        inv_id = self._get_invoice(app)
        with app.app_context():
            db.session.execute(db.delete(ExchangeRate))
            db.session.commit()
        login(client, "admin", "admin-pass")
        resp = client.post("/payments/add", data={
            "invoice_id": inv_id,
            "payment_date": "01.01.2020",
            "amount_eur": "50",
            "method": "cash",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_add_payment_exceeds_remaining(self, client, app):
        inv_id = self._get_invoice(app)
        login(client, "admin", "admin-pass")
        resp = client.post("/payments/add", data={
            "invoice_id": inv_id,
            "payment_date": date.today().strftime("%d.%m.%Y"),
            "amount_eur": "99999",
            "method": "cash",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_add_payment_invalid_date(self, client, app):
        inv_id = self._get_invoice(app)
        login(client, "admin", "admin-pass")
        resp = client.post("/payments/add", data={
            "invoice_id": inv_id,
            "payment_date": "not-a-date",
            "amount_eur": "50",
            "method": "cash",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_delete_payment(self, client, app):
        inv_id = self._get_invoice(app)
        with app.app_context():
            inv = db.session.get(Invoice, inv_id)
            p = Payment(
                invoice_id=inv.id, payment_date=date.today(),
                amount_eur=50, amount_try=2000, exchange_rate=40,
                method=PaymentMethod.CASH,
            )
            db.session.add(p)
            db.session.commit()
            pid = p.id
        login(client, "admin", "admin-pass")
        resp = client.post(f"/payments/{pid}/delete", follow_redirects=False)
        assert resp.status_code == 302

    def test_payment_status_helpers(self, app):
        from app.routes.payments import _payment_status
        with app.app_context():
            p = _create_party(db.session)
            inv = _create_invoice(db.session, p.id)
            status = _payment_status(inv, Decimal("100.00"), date.today())
            assert status == "paid"

            status2 = _payment_status(inv, Decimal("50.00"), date.today())
            assert status2 in ("pending", "overdue")

            inv.due_date = date.today() - timedelta(days=5)
            db.session.flush()
            status3 = _payment_status(inv, Decimal("0.00"), date.today())
            assert status3 == "overdue"


# ============================================================
# parties.py (19% → 85%+)
# ============================================================

class TestParties:
    def test_list_parties(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/parties/")
        assert resp.status_code == 200

    def test_list_parties_with_search(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/parties/?search=Test")
        assert resp.status_code == 200

    def test_list_parties_with_type_filter(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/parties/")
        assert resp.status_code == 200

    def test_list_parties_invalid_type(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/parties/?type=invalid_type_xyz", follow_redirects=False)
        assert resp.status_code == 200

    def test_add_party_get(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/parties/add")
        assert resp.status_code == 200

    def test_add_party_post_success(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.post("/parties/add", data={
            "party_type": "company_customer",
            "name": "New Corp",
            "first_name": "",
            "last_name": "",
            "phone": "5559998877",
            "email": "corp@test.com",
            "address": "Istanbul",
            "tax_id": "1234567890",
            "notes": "Test note",
            "treatment_status": "active",
            "contact_person": "Ali Veli",
            "contact_phone": "5550001122",
            "is_active": "on",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_add_party_post_invalid_type(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.post("/parties/add", data={
            "party_type": "",
            "name": "Bad Party",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_add_party_invalid_dob(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.post("/parties/add", data={
            "party_type": "patient",
            "name": "Dob Test",
            "date_of_birth": "not-a-date",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_detail_party(self, client, app):
        with app.app_context():
            p = _create_party(db.session, name="Detail Test")
            pid = p.id
        login(client, "admin", "admin-pass")
        resp = client.get(f"/parties/{pid}")
        assert resp.status_code == 200

    def test_edit_party_get(self, client, app):
        with app.app_context():
            p = _create_party(db.session, name="Edit Test")
            pid = p.id
        login(client, "admin", "admin-pass")
        resp = client.get(f"/parties/{pid}/edit")
        assert resp.status_code == 200

    def test_edit_party_post(self, client, app):
        with app.app_context():
            p = _create_party(db.session, name="Edit Post Test")
            pid = p.id
        login(client, "admin", "admin-pass")
        resp = client.post(f"/parties/{pid}/edit", data={
            "party_type": "patient",
            "name": "Edited Party",
            "first_name": "Edited",
            "last_name": "Party",
            "phone": "5550000000",
            "email": "edited@test.com",
            "treatment_status": "active",
            "is_active": "on",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_edit_party_invalid_type(self, client, app):
        with app.app_context():
            p = _create_party(db.session)
            pid = p.id
        login(client, "admin", "admin-pass")
        resp = client.post(f"/parties/{pid}/edit", data={
            "party_type": "",
            "name": "X",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_edit_party_invalid_dob(self, client, app):
        with app.app_context():
            p = _create_party(db.session)
            pid = p.id
        login(client, "admin", "admin-pass")
        resp = client.post(f"/parties/{pid}/edit", data={
            "party_type": "patient",
            "name": "X",
            "date_of_birth": "bad-date",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_delete_party(self, client, app):
        with app.app_context():
            p = _create_party(db.session, name="Delete Me")
            pid = p.id
        login(client, "admin", "admin-pass")
        resp = client.post(f"/parties/{pid}/delete", follow_redirects=False)
        assert resp.status_code == 302

    def test_add_party_company_name_fallback(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.post("/parties/add", data={
            "party_type": "company_customer",
            "company_name": "Company From Name",
            "name": "",
        }, follow_redirects=False)
        assert resp.status_code == 302


# ============================================================
# patients.py (25% → 85%+)
# ============================================================

class TestPatients:
    def test_list_patients(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/patients/", follow_redirects=False)
        assert resp.status_code == 302

    def test_list_patients_search(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/patients/?search=Ayse", follow_redirects=False)
        assert resp.status_code == 302

    def test_add_patient_get(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/patients/add")
        assert resp.status_code == 404

    def test_add_patient_post(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.post("/patients/add", data={
            "first_name": "Mehmet",
            "last_name": "Demir",
            "phone": "5551110000",
            "email": "mehmet@test.com",
            "address": "Ankara",
            "notes": "Note",
            "treatment_status": "active",
        }, follow_redirects=False)
        assert resp.status_code == 404

    def test_detail_patient(self, client, app):
        with app.app_context():
            p = _create_party(db.session, party_type=PartyType.DENTIST, name="Patient Detail")
            pid = p.id
        login(client, "admin", "admin-pass")
        resp = client.get(f"/patients/{pid}", follow_redirects=False)
        assert resp.status_code == 302

    def test_detail_non_patient_redirects(self, client, app):
        with app.app_context():
            p = _create_party(db.session, party_type=PartyType.DENTIST, name="Company")
            pid = p.id
        login(client, "admin", "admin-pass")
        resp = client.get(f"/patients/{pid}", follow_redirects=False)
        assert resp.status_code == 302

    def test_edit_patient_get(self, client, app):
        with app.app_context():
            p = _create_party(db.session, party_type=PartyType.DENTIST, name="Patient Edit")
            pid = p.id
        login(client, "admin", "admin-pass")
        resp = client.get(f"/patients/{pid}/edit")
        assert resp.status_code == 404

    def test_edit_patient_post(self, client, app):
        with app.app_context():
            p = _create_party(db.session, party_type=PartyType.DENTIST, name="Patient Edit Post")
            pid = p.id
        login(client, "admin", "admin-pass")
        resp = client.post(f"/patients/{pid}/edit", data={
            "first_name": "Updated",
            "last_name": "Patient",
            "phone": "5550009999",
            "email": "updated@test.com",
            "treatment_status": "active",
        }, follow_redirects=False)
        assert resp.status_code == 404

    def test_delete_patient(self, client, app):
        with app.app_context():
            p = _create_party(db.session, party_type=PartyType.DENTIST, name="Patient Delete")
            pid = p.id
        login(client, "admin", "admin-pass")
        resp = client.post(f"/patients/{pid}/delete", follow_redirects=False)
        assert resp.status_code == 404

    def test_add_patient_treatment(self, client, app):
        with app.app_context():
            p = _create_party(db.session, party_type=PartyType.DENTIST, name="Patient Treat")
            pid = p.id
            t = db.session.execute(db.select(Treatment).limit(1)).scalar_one()
            tid = t.id
        login(client, "admin", "admin-pass")
        resp = client.post(f"/patients/{pid}/add-treatment", data={
            "treatment_id": tid,
            "treatment_date": date.today().strftime("%d.%m.%Y"),
            "notes": "Test notes",
            "price_override": "75.50",
        }, follow_redirects=False)
        assert resp.status_code == 404

    def test_add_patient_treatment_missing_fields(self, client, app):
        with app.app_context():
            p = _create_party(db.session, party_type=PartyType.DENTIST, name="No Fields")
            pid = p.id
        login(client, "admin", "admin-pass")
        resp = client.post(f"/patients/{pid}/add-treatment", data={
            "treatment_id": "",
            "treatment_date": "",
        }, follow_redirects=False)
        assert resp.status_code == 404

    def test_add_patient_treatment_invalid_date(self, client, app):
        with app.app_context():
            p = _create_party(db.session, party_type=PartyType.DENTIST, name="Bad Date")
            pid = p.id
            t = db.session.execute(db.select(Treatment).limit(1)).scalar_one()
            tid = t.id
        login(client, "admin", "admin-pass")
        resp = client.post(f"/patients/{pid}/add-treatment", data={
            "treatment_id": tid,
            "treatment_date": "not-a-date",
        }, follow_redirects=False)
        assert resp.status_code == 404


# ============================================================
# treatments.py (47% → 85%+)
# ============================================================

class TestTreatments:
    def test_list_treatments(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/treatments/")
        assert resp.status_code == 200

    def test_list_treatments_with_category(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/treatments/?category=ekstra_islemler")
        assert resp.status_code == 200

    def test_list_treatments_with_search(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/treatments/?search=Crown")
        assert resp.status_code == 200

    def test_add_treatment_get(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/treatments/add")
        assert resp.status_code == 200

    def test_add_treatment_post(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.post("/treatments/add", data={
            "name": "New Treatment",
            "description": "A new treatment",
            "category": "ana_islemler",
            "price_eur": "150.00",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_add_treatment_validation_error(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.post("/treatments/add", data={
            "name": "",
            "category": "invalid",
            "price_eur": "abc",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_add_treatment_empty_name(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.post("/treatments/add", data={
            "name": "",
            "category": "ana_islemler",
            "price_eur": "100",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_add_treatment_long_name(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.post("/treatments/add", data={
            "name": "A" * 201,
            "category": "ana_islemler",
            "price_eur": "100",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_add_treatment_long_description(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.post("/treatments/add", data={
            "name": "Valid Name",
            "category": "ana_islemler",
            "price_eur": "100",
            "description": "D" * 2001,
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_add_treatment_negative_price(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.post("/treatments/add", data={
            "name": "Neg Price",
            "category": "ana_islemler",
            "price_eur": "-50",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_add_treatment_non_numeric_price(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.post("/treatments/add", data={
            "name": "NonNum",
            "category": "ana_islemler",
            "price_eur": "not-a-number",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_edit_treatment_get(self, client, app):
        with app.app_context():
            t = db.session.execute(db.select(Treatment).limit(1)).scalar_one()
            tid = t.id
        login(client, "admin", "admin-pass")
        resp = client.get(f"/treatments/{tid}/edit")
        assert resp.status_code == 200

    def test_edit_treatment_post(self, client, app):
        with app.app_context():
            t = db.session.execute(db.select(Treatment).limit(1)).scalar_one()
            tid = t.id
        login(client, "admin", "admin-pass")
        resp = client.post(f"/treatments/{tid}/edit", data={
            "name": "Updated Treatment",
            "category": "ekstra_islemler",
            "price_eur": "250",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_edit_treatment_validation_error(self, client, app):
        with app.app_context():
            t = db.session.execute(db.select(Treatment).limit(1)).scalar_one()
            tid = t.id
        login(client, "admin", "admin-pass")
        resp = client.post(f"/treatments/{tid}/edit", data={
            "name": "",
            "category": "bad",
            "price_eur": "xyz",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_delete_treatment(self, client, app):
        with app.app_context():
            t = db.session.execute(db.select(Treatment).limit(1)).scalar_one()
            tid = t.id
        login(client, "admin", "admin-pass")
        resp = client.post(f"/treatments/{tid}/delete", follow_redirects=False)
        assert resp.status_code == 302

    def test_import_treatments_get(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/treatments/import")
        assert resp.status_code == 200

    def test_import_treatments_no_file(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.post("/treatments/import", data={}, follow_redirects=False)
        assert resp.status_code == 302

    def test_import_treatments_wrong_extension(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.post("/treatments/import", data={
            "file": (io.BytesIO(b"test"), "test.csv"),
        }, content_type="multipart/form-data", follow_redirects=False)
        assert resp.status_code == 302

    def test_import_treatments_xlsx(self, client, app):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["Name", "Category", "Price", "Description"])
        ws.append(["Imported Treatment", "ana_islemler", 120.50, "Imported desc"])
        ws.append(["", "", "", ""])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        wb.close()

        login(client, "admin", "admin-pass")
        resp = client.post("/treatments/import", data={
            "file": (buf, "treatments.xlsx"),
        }, content_type="multipart/form-data", follow_redirects=False)
        assert resp.status_code == 302

    def test_import_treatments_update_existing(self, client, app):
        from openpyxl import Workbook
        with app.app_context():
            t = db.session.execute(db.select(Treatment).limit(1)).scalar_one()
            existing_name = t.name

        wb = Workbook()
        ws = wb.active
        ws.append(["Name", "Category", "Price", "Description"])
        ws.append([existing_name, "ana_islemler", 999.99, "Updated via import"])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        wb.close()

        login(client, "admin", "admin-pass")
        resp = client.post("/treatments/import", data={
            "file": (buf, "update.xlsx"),
        }, content_type="multipart/form-data", follow_redirects=False)
        assert resp.status_code == 302

    def test_api_update_treatment(self, client, app):
        with app.app_context():
            t = db.session.execute(db.select(Treatment).limit(1)).scalar_one()
            tid = t.id
        login(client, "admin", "admin-pass")
        resp = client.post("/treatments/api/update",
            data=json.dumps({"id": tid, "name": "API Updated", "price_eur": 300, "category": "ana_islemler"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_api_update_treatment_invalid_request(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.post("/treatments/api/update",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_api_update_treatment_not_found(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.post("/treatments/api/update",
            data=json.dumps({"id": 99999}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_api_update_treatment_invalid_price(self, client, app):
        with app.app_context():
            t = db.session.execute(db.select(Treatment).limit(1)).scalar_one()
            tid = t.id
        login(client, "admin", "admin-pass")
        resp = client.post("/treatments/api/update",
            data=json.dumps({"id": tid, "price_eur": "abc"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_api_update_with_turkish_category(self, client, app):
        with app.app_context():
            t = db.session.execute(db.select(Treatment).limit(1)).scalar_one()
            tid = t.id
        login(client, "admin", "admin-pass")
        resp = client.post("/treatments/api/update",
            data=json.dumps({"id": tid, "category": "ekstra_islemler"}),
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_api_update_description(self, client, app):
        with app.app_context():
            t = db.session.execute(db.select(Treatment).limit(1)).scalar_one()
            tid = t.id
        login(client, "admin", "admin-pass")
        resp = client.post("/treatments/api/update",
            data=json.dumps({"id": tid, "description": ""}),
            content_type="application/json",
        )
        assert resp.status_code == 200


# ============================================================
# invoices.py (56% → 85%+)
# ============================================================

class TestInvoices:
    def _party_id(self, app):
        with app.app_context():
            p = _create_party(db.session, name="Invoice Party")
            return p.id

    def test_list_invoices(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/invoices/")
        assert resp.status_code == 200

    def test_list_invoices_with_status(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/invoices/?status=pending")
        assert resp.status_code == 200

    def test_list_invoices_with_search(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/invoices/?search=MKR")
        assert resp.status_code == 200

    def test_list_invoices_with_category(self, client, app):
        pid = self._party_id(app)
        with app.app_context():
            t = db.session.execute(db.select(Treatment).limit(1)).scalar_one()
            InvoiceService.create_invoice(
                session=db.session, party_id=pid,
                items=[{"item_type": "treatment", "treatment_id": t.id, "description": t.name, "quantity": 1, "unit_price_eur": float(t.price_eur)}],
                invoice_date=date.today(),
            )
        login(client, "admin", "admin-pass")
        resp = client.get(f"/invoices/?category=other")
        assert resp.status_code == 200

    def test_list_invoices_mixed_category(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/invoices/?category=mixed")
        assert resp.status_code == 200

    def test_add_invoice_get(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/invoices/add")
        assert resp.status_code == 200

    def test_add_invoice_post_items_json(self, client, app):
        pid = self._party_id(app)
        login(client, "admin", "admin-pass")
        items = json.dumps([{"item_type": "service", "description": "Test Service", "quantity": 1, "unit_price_eur": 100}])
        resp = client.post("/invoices/add", data={
            "party_id": pid,
            "invoice_date": date.today().strftime("%d.%m.%Y"),
            "items_json": items,
            "notes": "Test invoice",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_add_invoice_post_no_items(self, client, app):
        pid = self._party_id(app)
        login(client, "admin", "admin-pass")
        resp = client.post("/invoices/add", data={
            "party_id": pid,
            "invoice_date": date.today().strftime("%d.%m.%Y"),
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_add_invoice_post_no_party(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.post("/invoices/add", data={
            "party_id": "",
            "items_json": json.dumps([{"item_type": "service", "description": "X", "quantity": 1, "unit_price_eur": 50}]),
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_add_invoice_invalid_date(self, client, app):
        pid = self._party_id(app)
        login(client, "admin", "admin-pass")
        resp = client.post("/invoices/add", data={
            "party_id": pid,
            "invoice_date": "not-a-date",
            "items_json": json.dumps([{"item_type": "service", "description": "X", "quantity": 1, "unit_price_eur": 50}]),
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_add_invoice_with_treatment_ids(self, client, app):
        pid = self._party_id(app)
        with app.app_context():
            p = db.session.get(Party, pid)
            patient = db.session.execute(db.select(Patient).limit(1)).scalar_one()
            t = db.session.execute(db.select(Treatment).limit(1)).scalar_one()
            pt = PatientTreatment(
                party_id=pid, patient_id=patient.id, treatment_id=t.id,
                treatment_date=date.today(),
            )
            db.session.add(pt)
            db.session.commit()
            pt_id = pt.id
        login(client, "admin", "admin-pass")
        resp = client.post("/invoices/add", data={
            "party_id": pid,
            "invoice_date": date.today().strftime("%d.%m.%Y"),
            "treatment_ids": [pt_id],
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_detail_invoice(self, client, app):
        pid = self._party_id(app)
        with app.app_context():
            inv = _create_invoice(db.session, pid)
            inv_id = inv.id
        login(client, "admin", "admin-pass")
        resp = client.get(f"/invoices/{inv_id}")
        assert resp.status_code == 200

    def test_download_pdf(self, client, app):
        pid = self._party_id(app)
        with app.app_context():
            inv = _create_invoice(db.session, pid)
            inv_id = inv.id
        login(client, "admin", "admin-pass")
        resp = client.get(f"/invoices/{inv_id}/pdf")
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"

    def test_update_status(self, client, app):
        pid = self._party_id(app)
        with app.app_context():
            inv = _create_invoice(db.session, pid)
            inv_id = inv.id
        login(client, "admin", "admin-pass")
        resp = client.post(f"/invoices/{inv_id}/status", data={"status": "cancelled"}, follow_redirects=False)
        assert resp.status_code == 302

    def test_update_status_to_paid_auto_payment(self, client, app):
        pid = self._party_id(app)
        with app.app_context():
            inv = _create_invoice(db.session, pid, items=[
                {"item_type": "service", "description": "AutoPay", "quantity": 1, "unit_price_eur": 100}
            ])
            inv_id = inv.id
        login(client, "admin", "admin-pass")
        resp = client.post(f"/invoices/{inv_id}/status", data={"status": "paid"}, follow_redirects=False)
        assert resp.status_code == 302

    def test_send_email(self, client, app):
        pid = self._party_id(app)
        with app.app_context():
            p = db.session.get(Party, pid)
            p.email = "test@example.com"
            db.session.flush()
            inv = _create_invoice(db.session, pid)
            inv_id = inv.id
        login(client, "admin", "admin-pass")
        with patch("app.services.email_service.get_smtp_config", return_value={"smtp_server": "x", "smtp_port": "587", "smtp_username": "", "smtp_password": ""}):
            resp = client.post(f"/invoices/{inv_id}/send-email", follow_redirects=False)
            assert resp.status_code == 302

    def test_delete_invoice(self, client, app):
        pid = self._party_id(app)
        with app.app_context():
            inv = _create_invoice(db.session, pid)
            inv_id = inv.id
        login(client, "admin", "admin-pass")
        resp = client.post(f"/invoices/{inv_id}/delete", follow_redirects=False)
        assert resp.status_code == 302

    def test_api_treatment_price(self, client, app):
        with app.app_context():
            pt = db.session.execute(db.select(PatientTreatment).limit(1)).scalar_one()
            pt_id = pt.id
        login(client, "admin", "admin-pass")
        resp = client.get(f"/invoices/api/treatment-price/{pt_id}")
        assert resp.status_code == 200

    def test_api_treatment_price_not_found(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/invoices/api/treatment-price/99999")
        assert resp.status_code == 404

    def test_api_party_info(self, client, app):
        pid = self._party_id(app)
        login(client, "admin", "admin-pass")
        resp = client.get(f"/invoices/api/party/{pid}")
        assert resp.status_code == 200

    def test_api_party_info_not_found(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/invoices/api/party/99999")
        assert resp.status_code == 404

    def test_api_exchange_rate(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get(f"/invoices/api/exchange-rate?date={date.today().isoformat()}")
        assert resp.status_code == 200

    def test_api_exchange_rate_invalid_date(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/invoices/api/exchange-rate?date=bad")
        assert resp.status_code == 400

    def test_api_exchange_rate_no_rate(self, client, app):
        with app.app_context():
            db.session.execute(db.delete(ExchangeRate))
            db.session.commit()
        login(client, "admin", "admin-pass")
        resp = client.get(f"/invoices/api/exchange-rate?date={date.today().isoformat()}")
        assert resp.status_code == 404

    def test_add_invoice_legacy_patient_id(self, client, app):
        pid = self._party_id(app)
        with app.app_context():
            party = db.session.get(Party, pid)
            patient = db.session.execute(db.select(Patient).limit(1)).scalar_one()
            patient.party_id = pid
            db.session.commit()
            patient_id = patient.id
        login(client, "admin", "admin-pass")
        items = json.dumps([{"item_type": "service", "description": "Legacy", "quantity": 1, "unit_price_eur": 100}])
        resp = client.post("/invoices/add", data={
            "patient_id": patient_id,
            "invoice_date": date.today().strftime("%d.%m.%Y"),
            "items_json": items,
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_add_invoice_value_error(self, client, app):
        pid = self._party_id(app)
        login(client, "admin", "admin-pass")
        resp = client.post("/invoices/add", data={
            "party_id": pid,
            "invoice_date": date.today().strftime("%d.%m.%Y"),
            "items_json": json.dumps([{"item_type": "service", "description": "", "quantity": 1, "unit_price_eur": 100}]),
        }, follow_redirects=False)
        assert resp.status_code == 302


# ============================================================
# reports.py (56% → 85%+)
# ============================================================

class TestReports:
    def test_index_default(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/reports/")
        assert resp.status_code == 200

    def test_index_last_30(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/reports/?period=last_30")
        assert resp.status_code == 200

    def test_index_this_year(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/reports/?period=this_year")
        assert resp.status_code == 200

    def test_index_last_year(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/reports/?period=last_year")
        assert resp.status_code == 200

    def test_index_custom_period(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/reports/?period=custom&start_date=01.01.2024&end_date=31.12.2024")
        assert resp.status_code == 200

    def test_index_custom_start_only(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/reports/?period=custom&start_date=01.06.2024")
        assert resp.status_code == 200

    def test_index_custom_end_only(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/reports/?period=custom&end_date=31.12.2024")
        assert resp.status_code == 200

    def test_index_swapped_dates(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/reports/?period=custom&start_date=31.12.2024&end_date=01.01.2024")
        assert resp.status_code == 200

    def test_index_with_data(self, client, app):
        pid = None
        with app.app_context():
            p = _create_party(db.session, name="Report Party")
            pid = p.id
            inv = _create_invoice(db.session, pid)
            Payment(
                invoice_id=inv.id, payment_date=date.today(),
                amount_eur=50, amount_try=2000, exchange_rate=40,
                method=PaymentMethod.CASH,
            )
            db.session.add(Payment(
                invoice_id=inv.id, payment_date=date.today(),
                amount_eur=50, amount_try=2000, exchange_rate=40,
                method=PaymentMethod.CASH,
            ))
            db.session.commit()
        login(client, "admin", "admin-pass")
        resp = client.get("/reports/?period=this_month")
        assert resp.status_code == 200


# ============================================================
# auth.py (83% → 90%+)
# ============================================================

class TestAuth:
    def test_login_lockout(self, client, app):
        for _ in range(5):
            client.post("/login", data={"username": "admin", "password": "wrong"})
        resp = client.post("/login", data={"username": "admin", "password": "wrong"}, follow_redirects=True)
        assert b"15 dakika" in resp.data or b"denemesi" in resp.data

    def test_login_already_authenticated(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/login", follow_redirects=False)
        assert resp.status_code == 302

    def test_login_bad_password(self, client, app):
        resp = client.post("/login", data={"username": "admin", "password": "wrong"})
        assert resp.status_code == 200

    def test_login_no_user(self, client, app):
        resp = client.post("/login", data={"username": "nonexistent", "password": "x"})
        assert resp.status_code == 200

    def test_safe_redirect(self, client, app):
        from app.routes.auth import _is_safe_redirect_url
        with app.test_request_context("http://localhost:5000/"):
            assert _is_safe_redirect_url("/dashboard") is True
            assert _is_safe_redirect_url("http://evil.com") is False
            assert _is_safe_redirect_url("") is False
            assert _is_safe_redirect_url(None) is False

    def test_login_with_next_safe(self, client, app):
        resp = client.post("/login?next=/", data={"username": "admin", "password": "admin-pass"}, follow_redirects=False)
        assert resp.status_code == 302

    def test_login_with_next_unsafe(self, client, app):
        resp = client.post("/login?next=http://evil.com", data={"username": "admin", "password": "admin-pass"}, follow_redirects=False)
        assert resp.status_code == 302


# ============================================================
# __init__.py (73% → 85%+)
# ============================================================

class TestInit:
    def test_context_processor(self, client, app):
        login(client, "admin", "admin-pass")
        resp = client.get("/")
        assert resp.status_code == 200

    def test_context_processor_exception(self, client, app):
        login(client, "admin", "admin-pass")
        from app.services import exchange_service
        with patch.object(exchange_service, "get_rate_health", side_effect=Exception("rate error")):
            resp = client.get("/")
            assert resp.status_code == 200

    def test_refresh_exchange_rate_cli(self, app):
        with patch(
            "app.services.exchange_service.fetch_and_store_rate",
            return_value=Decimal("42.1234"),
        ) as fetch_rate:
            runner = app.test_cli_runner()
            result = runner.invoke(args=["refresh-exchange-rate"])

        assert result.exit_code == 0
        assert "EUR/TRY rate stored: 42.1234" in result.output
        fetch_rate.assert_called_once_with()

    def test_purge_audit_logs_cli(self, app):
        with app.app_context():
            from app import create_app
            runner = app.test_cli_runner()
            result = runner.invoke(args=["purge-expired-audit-logs"])
            assert result.exit_code == 0


# ============================================================
# security_service.py (71% → 85%+)
# ============================================================

class TestSecurityService:
    def test_encrypt_decrypt_roundtrip(self, app):
        from app.services.security_service import encrypt_value, decrypt_value
        with app.app_context():
            encrypted = encrypt_value("hello-world")
            assert encrypted != "hello-world"
            decrypted = decrypt_value(encrypted)
            assert decrypted == "hello-world"

    def test_encrypt_empty(self, app):
        from app.services.security_service import encrypt_value
        with app.app_context():
            assert encrypt_value("") == ""

    def test_decrypt_empty(self, app):
        from app.services.security_service import decrypt_value
        with app.app_context():
            assert decrypt_value("") == ""

    def test_decrypt_invalid(self, app):
        from app.services.security_service import decrypt_value
        with app.app_context():
            with pytest.raises(ValueError, match="Failed to decrypt"):
                decrypt_value("not-a-valid-token")

    def test_no_encryption_key(self, app):
        from app.services.security_service import _get_fernet
        with app.app_context():
            app.config["ENCRYPTION_KEY"] = ""
            app.config["SECRET_KEY"] = ""
            with pytest.raises(RuntimeError):
                _get_fernet()


# ============================================================
# email_service.py full paths
# ============================================================

class TestEmailServiceFull:
    def test_send_email_success(self, client, app):
        with app.app_context():
            p = _create_party(db.session, name="Email Party", email="recv@test.com", party_type=PartyType.DENTIST)
            inv = _create_invoice(db.session, p.id)
            with patch("app.services.email_service.get_smtp_config", return_value={
                "smtp_server": "localhost", "smtp_port": "587",
                "smtp_username": "sender@test.com", "smtp_password": "testpass",
            }):
                with patch("app.services.email_service.smtplib.SMTP") as mock_smtp:
                    mock_server = MagicMock()
                    mock_smtp.return_value = mock_server
                    from app.services.email_service import send_invoice_email
                    success, msg = send_invoice_email(inv)
                    assert success is True

    def test_send_email_value_error(self, client, app):
        with app.app_context():
            p = _create_party(db.session, name="VE Party", email="ve@test.com", party_type=PartyType.DENTIST)
            inv = _create_invoice(db.session, p.id)
            with patch("app.services.email_service.get_smtp_config", side_effect=ValueError("Decrypt failed")):
                from app.services.email_service import send_invoice_email
                success, msg = send_invoice_email(inv)
                assert success is False
                assert "çözülemedi" in msg

    def test_send_email_generic_exception(self, client, app):
        with app.app_context():
            p = _create_party(db.session, name="Exc Party", email="exc@test.com", party_type=PartyType.DENTIST)
            inv = _create_invoice(db.session, p.id)
            with patch("app.services.email_service.get_smtp_config", side_effect=Exception("SMTP down")):
                from app.services.email_service import send_invoice_email
                success, msg = send_invoice_email(inv)
                assert success is False

    def test_send_email_legacy_patient(self, client, app):
        with app.app_context():
            from app.models.models import Patient
            patient = db.session.execute(db.select(Patient).limit(1)).scalar_one()
            patient.email = "legacy@test.com"
            party = patient.party
            party.email = None
            db.session.flush()
            inv = _create_invoice(db.session, party.id)
            inv.patient_id = patient.id
            db.session.flush()
            with patch("app.services.email_service.get_smtp_config", return_value={
                "smtp_server": "localhost", "smtp_port": "587",
                "smtp_username": "s@test.com", "smtp_password": "pass",
            }):
                with patch("app.services.email_service.smtplib.SMTP"):
                    from app.services.email_service import send_invoice_email
                    success, msg = send_invoice_email(inv)
                    assert success is True


# ============================================================
# pdf_service.py extra paths
# ============================================================

class TestPdfServiceExtra:
    def test_pdf_no_notes(self, client, app):
        with app.app_context():
            p = _create_party(db.session, name="PDF No Notes")
            inv = _create_invoice(db.session, p.id)
            inv.notes = None
            db.session.flush()
            from app.services.pdf_service import generate_invoice_pdf
            pdf = generate_invoice_pdf(inv)
            assert pdf[:4] == b"%PDF"

    def test_pdf_long_notes(self, client, app):
        with app.app_context():
            p = _create_party(db.session, name="PDF Long Notes")
            inv = _create_invoice(db.session, p.id, notes="N" * 500)
            from app.services.pdf_service import generate_invoice_pdf
            pdf = generate_invoice_pdf(inv)
            assert pdf[:4] == b"%PDF"

    def test_get_customer_info_no_party(self, client, app):
        from app.services.pdf_service import get_customer_info
        inv = MagicMock()
        inv.party = None
        inv.patient = None
        info = get_customer_info(inv)
        assert info["name"] == "Bilinmeyen müşteri"

    def test_get_customer_info_party(self, client, app):
        from app.services.pdf_service import get_customer_info
        inv = MagicMock()
        party = MagicMock()
        party.display_name = "Test Party"
        party.phone = "555"
        party.email = "t@t.com"
        party.address = "Addr"
        party.tax_id = "123"
        inv.party = party
        inv.patient = None
        info = get_customer_info(inv)
        assert info["name"] == "Test Party"

    def test_invoice_pdf_header_fallback(self, client, app):
        from app.services.pdf_service import InvoicePDF
        with patch("app.services.pdf_service.os.path.exists", return_value=False):
            pdf = InvoicePDF()
            assert pdf.default_font == "Helvetica"

    def test_pdf_with_footer_text(self, client, app):
        from app.services.pdf_service import InvoicePDF
        pdf = InvoicePDF(footer_text="Custom footer text")
        pdf.add_page()
        pdf.add_notes("Test notes")
        output = pdf.output()
        assert len(output) > 0

    def test_pdf_no_footer_text(self, client, app):
        from app.services.pdf_service import InvoicePDF
        pdf = InvoicePDF(footer_text="")
        pdf.add_page()
        assert len(pdf.output()) > 0


# ============================================================
# invoice_service.py (73% → 90%+)
# ============================================================

class TestInvoiceServiceValidation:
    def test_normalize_item_empty_description(self):
        from app.models.invoice_service import _normalize_item
        with pytest.raises(ValueError, match="açıklaması"):
            _normalize_item({"description": "", "quantity": 1, "unit_price_eur": 100})

    def test_normalize_item_long_description(self):
        from app.models.invoice_service import _normalize_item
        with pytest.raises(ValueError, match="300"):
            _normalize_item({"description": "D" * 301, "quantity": 1, "unit_price_eur": 100})

    def test_normalize_item_bad_quantity(self):
        from app.models.invoice_service import _normalize_item
        with pytest.raises(ValueError, match="Miktar"):
            _normalize_item({"description": "Test", "quantity": "abc", "unit_price_eur": 100})

    def test_normalize_item_zero_quantity(self):
        from app.models.invoice_service import _normalize_item
        with pytest.raises(ValueError, match="büyük"):
            _normalize_item({"description": "Test", "quantity": 0, "unit_price_eur": 100})

    def test_normalize_item_bad_price(self):
        from app.models.invoice_service import _normalize_item
        with pytest.raises(ValueError, match="say"):
            _normalize_item({"description": "Test", "quantity": 1, "unit_price_eur": "abc"})

    def test_normalize_item_negative_price(self):
        from app.models.invoice_service import _normalize_item
        with pytest.raises(ValueError, match="negatif"):
            _normalize_item({"description": "Test", "quantity": 1, "unit_price_eur": -50})

    def test_normalize_item_bad_vat(self):
        from app.models.invoice_service import _normalize_item
        with pytest.raises(ValueError, match="KDV"):
            _normalize_item({"description": "Test", "quantity": 1, "unit_price_eur": 100, "vat_rate": "abc"})

    def test_normalize_item_vat_over_100(self):
        from app.models.invoice_service import _normalize_item
        with pytest.raises(ValueError, match="100"):
            _normalize_item({"description": "Test", "quantity": 1, "unit_price_eur": 100, "vat_rate": 150})

    def test_normalize_item_bad_discount_type(self):
        from app.models.invoice_service import _normalize_item
        with pytest.raises(ValueError, match="skonto tipi"):
            _normalize_item({"description": "Test", "quantity": 1, "unit_price_eur": 100, "discount_type": "bad"})

    def test_normalize_item_bad_discount_value(self):
        from app.models.invoice_service import _normalize_item
        with pytest.raises(ValueError, match="say"):
            _normalize_item({"description": "Test", "quantity": 1, "unit_price_eur": 100, "discount_value": "abc"})

    def test_normalize_item_percent_over_100(self):
        from app.models.invoice_service import _normalize_item
        with pytest.raises(ValueError, match="aşamaz"):
            _normalize_item({"description": "Test", "quantity": 1, "unit_price_eur": 100, "discount_type": "percent", "discount_value": 150})

    def test_normalize_item_amount_discount_too_high(self):
        from app.models.invoice_service import _normalize_item
        with pytest.raises(ValueError, match="aşamaz"):
            _normalize_item({"description": "Test", "quantity": 1, "unit_price_eur": 100, "discount_type": "amount", "discount_value": 200})

    def test_normalize_item_bad_item_type(self):
        from app.models.invoice_service import _normalize_item
        with pytest.raises(ValueError, match="Geçersiz"):
            _normalize_item({"description": "Test", "quantity": 1, "unit_price_eur": 100, "item_type": "badtype"})

    def test_create_invoice_no_items(self, app):
        with app.app_context():
            p = _create_party(db.session)
            with pytest.raises(ValueError, match="bir kalem"):
                InvoiceService.create_invoice(db.session, p.id, [])

    def test_create_invoice_bad_party(self, app):
        with app.app_context():
            with pytest.raises(ValueError, match="bulunamadı"):
                InvoiceService.create_invoice(db.session, 99999, [{"item_type": "service", "description": "X", "quantity": 1, "unit_price_eur": 100}])

    def test_create_invoice_treatment_no_treatment_id(self, app):
        with app.app_context():
            p = _create_party(db.session)
            with pytest.raises(ValueError, match="tedavi"):
                InvoiceService.create_invoice(db.session, p.id, [
                    {"item_type": "treatment", "description": "NoTID", "quantity": 1, "unit_price_eur": 100}
                ])

    def test_create_invoice_treatment_bad_id(self, app):
        with app.app_context():
            p = _create_party(db.session)
            with pytest.raises(ValueError, match="tedavi"):
                InvoiceService.create_invoice(db.session, p.id, [
                    {"item_type": "treatment", "treatment_id": 99999, "description": "BadTID", "quantity": 1, "unit_price_eur": 100}
                ])

    def test_create_invoice_from_treatments_not_found(self, app):
        with app.app_context():
            p = _create_party(db.session)
            with pytest.raises(ValueError, match="not found"):
                InvoiceService.create_invoice_from_treatments(db.session, p.id, [99999])

    def test_get_exchange_rate_no_rate(self, app):
        with app.app_context():
            db.session.execute(db.delete(ExchangeRate))
            db.session.commit()
            with pytest.raises(ValueError, match="No exchange rate"):
                InvoiceService.get_exchange_rate(db.session, date(2020, 1, 1))


# ============================================================
# payments.py edge cases
# ============================================================

class TestPaymentsEdgeCases:
    def test_add_payment_with_invalid_date_str(self, client, app):
        with app.app_context():
            p = _create_party(db.session, name="Pay Party")
            inv = _create_invoice(db.session, p.id)
            inv_id = inv.id
        login(client, "admin", "admin-pass")
        resp = client.post("/payments/add", data={
            "invoice_id": inv_id,
            "payment_date": "32.13.2024",
            "amount_eur": "50",
            "method": "card",
        }, follow_redirects=False)
        assert resp.status_code == 302


# ============================================================
# patients.py add-treatment with parse_float
# ============================================================

class TestPatientTreatments:
    def test_add_treatment_empty_price_override(self, client, app):
        with app.app_context():
            p = _create_party(db.session, party_type=PartyType.DENTIST, name="Empty Price")
            pid = p.id
            t = db.session.execute(db.select(Treatment).limit(1)).scalar_one()
            tid = t.id
        login(client, "admin", "admin-pass")
        resp = client.post(f"/patients/{pid}/add-treatment", data={
            "treatment_id": tid,
            "treatment_date": date.today().strftime("%d.%m.%Y"),
            "price_override": "",
        }, follow_redirects=False)
        assert resp.status_code == 404


# ============================================================
# invoice_service.py discount paths
# ============================================================

class TestInvoiceServiceDiscounts:
    def test_create_with_percent_discount(self, app):
        with app.app_context():
            p = _create_party(db.session)
            inv = InvoiceService.create_invoice(
                db.session, p.id,
                [{"item_type": "service", "description": "Disc", "quantity": 2, "unit_price_eur": 100,
                  "discount_type": "percent", "discount_value": 10}],
            )
            assert inv.total_eur > 0

    def test_create_with_amount_discount(self, app):
        with app.app_context():
            p = _create_party(db.session)
            inv = InvoiceService.create_invoice(
                db.session, p.id,
                [{"item_type": "service", "description": "AmtDisc", "quantity": 1, "unit_price_eur": 100,
                  "discount_type": "amount", "discount_value": 20}],
            )
            assert inv.total_eur > 0

    def test_create_with_vat(self, app):
        with app.app_context():
            p = _create_party(db.session)
            inv = InvoiceService.create_invoice(
                db.session, p.id,
                [{"item_type": "service", "description": "VAT", "quantity": 1, "unit_price_eur": 100, "vat_rate": 20}],
            )
            assert inv.total_eur > 0

    def test_create_product_item(self, app):
        with app.app_context():
            p = _create_party(db.session)
            inv = InvoiceService.create_invoice(
                db.session, p.id,
                [{"item_type": "product", "description": "Product", "quantity": 3, "unit_price_eur": 50}],
            )
            assert inv.total_eur > 0
