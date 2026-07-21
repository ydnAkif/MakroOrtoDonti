from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from app.extensions import db
from app.models.models import Party, PartyType, WorkOrder, Makbuz, Settings

from conftest import login


def _make_doctor(app, name="Dr. Test Makbuz", phone="+905551110099"):
    with app.app_context():
        party = Party(party_type=PartyType.DENTIST, name=name, phone=phone)
        db.session.add(party)
        db.session.commit()
        return party.id


def _add_work_order(app, party_id, work_date, apparatus_price, extra_price=0):
    with app.app_context():
        wo = WorkOrder(
            party_id=party_id, work_date=work_date, apparatus_type="Nance",
            patient_name="Test Hasta", apparatus_price=apparatus_price,
            extra_price=extra_price, total_price=apparatus_price + extra_price,
        )
        db.session.add(wo)
        db.session.commit()
        return wo.id


def test_list_makbuzlar_aggregates_per_doctor(client, app):
    login(client, "admin", "admin-pass")
    party_id = _make_doctor(app)
    _add_work_order(app, party_id, date(2026, 6, 10), 1000, extra_price=200)
    _add_work_order(app, party_id, date(2026, 6, 20), 500)

    response = client.get("/makbuzlar/?year=2026&month=6")
    assert response.status_code == 200
    assert "Dr. Test Makbuz".encode() in response.data

    # Doctors without work orders in the period are not listed
    empty = client.get("/makbuzlar/?year=2020&month=1")
    assert empty.status_code == 200
    assert "Dr. Test Makbuz".encode() not in empty.data


def test_edit_work_order_route(client, app):
    login(client, "admin", "admin-pass")
    party_id = _make_doctor(app, name="Dr. WO Edit", phone="+905551110098")
    wo_id = _add_work_order(app, party_id, date(2026, 6, 10), 1000)

    response = client.get(f"/parties/{party_id}/work-orders/{wo_id}/edit")
    assert response.status_code == 200

    response = client.post(
        f"/parties/{party_id}/work-orders/{wo_id}/edit",
        data={"work_date": "gecersiz-tarih"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    response = client.post(
        f"/parties/{party_id}/work-orders/{wo_id}/edit",
        data={
            "work_date": "2026-06-15",
            "apparatus_type": "Hyrax",
            "patient_name": "yENİ hASTA",
            "apparatus_price": "1500",
            "extra_price": "100",
            "exchange_rate_applied": "40",
            "notes": "güncellendi",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    with app.app_context():
        wo = db.session.get(WorkOrder, wo_id)
        assert wo.apparatus_type == "Hyrax"
        assert wo.patient_name == "Yeni Hasta"
        assert float(wo.total_price) == 1600.0


def test_work_orders_are_listed_newest_first_with_same_date_tiebreaker(client, app):
    login(client, "admin", "admin-pass")
    party_id = _make_doctor(app, name="Dr. Sıralama", phone="+905551110097")
    first_id = _add_work_order(app, party_id, date(2026, 6, 10), 1000)
    second_id = _add_work_order(app, party_id, date(2026, 6, 10), 1200)
    with app.app_context():
        db.session.get(WorkOrder, first_id).patient_name = "Aynı Gün İlk Kayıt"
        db.session.get(WorkOrder, second_id).patient_name = "Aynı Gün Son Kayıt"
        db.session.commit()

    html = client.get(f"/parties/{party_id}").get_data(as_text=True)
    assert html.index("Aynı Gün Son Kayıt") < html.index("Aynı Gün İlk Kayıt")


def test_generate_makbuz_computes_vat(client, app):
    login(client, "admin", "admin-pass")
    party_id = _make_doctor(app)
    _add_work_order(app, party_id, date(2026, 6, 10), 1000)
    _add_work_order(app, party_id, date(2026, 6, 20), 500)

    response = client.post(
        f"/makbuzlar/{party_id}/generate",
        data={"year": 2026, "month": 6, "vat_applied": "on", "vat_rate": "20"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        makbuz = db.session.execute(
            db.select(Makbuz).where(Makbuz.party_id == party_id, Makbuz.year == 2026, Makbuz.month == 6)
        ).scalar_one()
        assert makbuz.status == Makbuz.STATUS_DRAFT
        assert makbuz.work_order_count == 2
        assert makbuz.subtotal == Decimal("1500.00")
        assert makbuz.vat_amount == Decimal("300.00")
        assert makbuz.grand_total == Decimal("1800.00")


def test_party_detail_reflects_persisted_receipt_vat_and_formats_phone(client, app):
    login(client, "admin", "admin-pass")
    party_id = _make_doctor(
        app, name="Dr. KDV Özeti", phone="+905337694469"
    )
    _add_work_order(app, party_id, date(2026, 6, 10), 1000)
    client.post(
        f"/makbuzlar/{party_id}/generate",
        data={"year": 2026, "month": 6, "vat_applied": "on", "vat_rate": "20"},
        follow_redirects=False,
    )

    html = client.get(f"/parties/{party_id}").get_data(as_text=True)
    assert "+90 533 769 44 69" in html
    assert "KDV (makbuzlar): ₺200.00" in html
    assert "₺1,200.00" in html


def test_generate_makbuz_without_vat(client, app):
    login(client, "admin", "admin-pass")
    party_id = _make_doctor(app, name="Dr. No VAT")
    _add_work_order(app, party_id, date(2026, 6, 5), 750)

    client.post(
        f"/makbuzlar/{party_id}/generate",
        data={"year": 2026, "month": 6},
        follow_redirects=False,
    )

    with app.app_context():
        makbuz = db.session.execute(
            db.select(Makbuz).where(Makbuz.party_id == party_id)
        ).scalar_one()
        assert makbuz.vat_applied is False
        assert makbuz.vat_amount == Decimal("0.00")
        assert makbuz.grand_total == Decimal("750.00")


def test_makbuz_pdf_preview_and_download(client, app):
    login(client, "admin", "admin-pass")
    party_id = _make_doctor(app, name="Dr. PDF Önizleme")
    _add_work_order(app, party_id, date(2026, 6, 12), 1200, extra_price=300)
    client.post(f"/makbuzlar/{party_id}/generate", data={"year": 2026, "month": 6}, follow_redirects=False)

    with app.app_context():
        makbuz_id = db.session.execute(
            db.select(Makbuz.id).where(Makbuz.party_id == party_id)
        ).scalar_one()

    response = client.get(f"/makbuzlar/{makbuz_id}/pdf")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/pdf"
    assert "inline" in response.headers["Content-Disposition"]
    assert response.data.startswith(b"%PDF")

    response = client.get(f"/makbuzlar/{makbuz_id}/pdf?download=1")
    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    assert f"makbuz_2026_06_{party_id}.pdf" in response.headers["Content-Disposition"]


def test_cannot_regenerate_sent_makbuz(client, app):
    login(client, "admin", "admin-pass")
    party_id = _make_doctor(app, name="Dr. Locked")
    _add_work_order(app, party_id, date(2026, 6, 1), 1000)

    client.post(f"/makbuzlar/{party_id}/generate", data={"year": 2026, "month": 6}, follow_redirects=False)

    with app.app_context():
        makbuz = db.session.execute(db.select(Makbuz).where(Makbuz.party_id == party_id)).scalar_one()
        makbuz.status = Makbuz.STATUS_SENT
        db.session.commit()

    # Adding a new work order after send should not silently change the locked makbuz.
    _add_work_order(app, party_id, date(2026, 6, 15), 5000)
    response = client.post(
        f"/makbuzlar/{party_id}/generate",
        data={"year": 2026, "month": 6},
        follow_redirects=True,
    )
    assert "yeniden oluşturulamaz" in response.get_data(as_text=True)

    with app.app_context():
        makbuz = db.session.execute(db.select(Makbuz).where(Makbuz.party_id == party_id)).scalar_one()
        assert makbuz.subtotal == Decimal("1000.00")  # unchanged


def test_send_and_mark_paid_flow(client, app):
    login(client, "admin", "admin-pass")
    party_id = _make_doctor(app, name="Dr. Paid Flow")
    _add_work_order(app, party_id, date(2026, 6, 1), 2000)
    client.post(f"/makbuzlar/{party_id}/generate", data={"year": 2026, "month": 6}, follow_redirects=False)

    with app.app_context():
        makbuz_id = db.session.execute(db.select(Makbuz).where(Makbuz.party_id == party_id)).scalar_one().id

    with patch("app.services.whatsapp_service.WhatsAppService.send_makbuz_message", return_value={"success": True, "message": "ok"}):
        response = client.post(f"/makbuzlar/{makbuz_id}/send", follow_redirects=False)
        assert response.status_code == 302

    with app.app_context():
        assert db.session.get(Makbuz, makbuz_id).status == Makbuz.STATUS_SENT

    response = client.post(
        f"/payments/{makbuz_id}/mark-paid",
        data={"paid_at": date.today().isoformat(), "paid_amount": "2000.00", "payment_method": "cash"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        makbuz = db.session.get(Makbuz, makbuz_id)
        assert makbuz.status == Makbuz.STATUS_PAID
        assert makbuz.paid_amount == Decimal("2000.00")

    response = client.get("/payments/")
    assert response.status_code == 200
    assert "Dr. Paid Flow" in response.get_data(as_text=True)

    response = client.post(f"/payments/{makbuz_id}/unmark-paid", follow_redirects=False)
    assert response.status_code == 302
    with app.app_context():
        makbuz = db.session.get(Makbuz, makbuz_id)
        assert makbuz.status == Makbuz.STATUS_SENT
        assert makbuz.paid_amount is None


def test_send_failure_keeps_status(client, app):
    login(client, "admin", "admin-pass")
    party_id = _make_doctor(app, name="Dr. Send Fail")
    _add_work_order(app, party_id, date(2026, 6, 1), 500)
    client.post(f"/makbuzlar/{party_id}/generate", data={"year": 2026, "month": 6}, follow_redirects=False)

    with app.app_context():
        makbuz_id = db.session.execute(db.select(Makbuz).where(Makbuz.party_id == party_id)).scalar_one().id

    with patch("app.services.whatsapp_service.WhatsAppService.send_makbuz_message", return_value={"success": False, "message": "WhatsApp bağlı değil."}):
        client.post(f"/makbuzlar/{makbuz_id}/send", follow_redirects=False)

    with app.app_context():
        assert db.session.get(Makbuz, makbuz_id).status == Makbuz.STATUS_DRAFT


def test_bulk_generate_creates_drafts_without_sending(client, app):
    login(client, "admin", "admin-pass")
    p1 = _make_doctor(app, name="Dr. Bulk One", phone="+905551110001")
    p2 = _make_doctor(app, name="Dr. Bulk Two", phone="+905551110002")
    _add_work_order(app, p1, date(2026, 6, 3), 1000)
    _add_work_order(app, p2, date(2026, 6, 4), 2000)

    with patch("app.services.whatsapp_service.WhatsAppService.send_makbuz_message") as mock_send:
        response = client.post(
            "/makbuzlar/bulk-generate",
            data={
                "year": 2026, "month": 6,
                "party_ids": [str(p1), str(p2)],
                f"vat_{p1}_vat_applied": "on",
                f"vat_{p1}_vat_rate": "10",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        mock_send.assert_not_called()

    with app.app_context():
        m1 = db.session.execute(db.select(Makbuz).where(Makbuz.party_id == p1)).scalar_one()
        m2 = db.session.execute(db.select(Makbuz).where(Makbuz.party_id == p2)).scalar_one()
        assert m1.status == Makbuz.STATUS_DRAFT
        assert m1.vat_applied is True
        assert m1.grand_total == Decimal("1100.00")
        assert m2.status == Makbuz.STATUS_DRAFT
        assert m2.vat_applied is False

    list_html = client.get("/makbuzlar/?year=2026&month=6").get_data(as_text=True)
    p1_vat_control = list_html.split(f'id="vat-{p1}"', 1)[1].split(">", 1)[0]
    p2_vat_control = list_html.split(f'id="vat-{p2}"', 1)[1].split(">", 1)[0]
    assert "checked" in p1_vat_control
    assert "checked" not in p2_vat_control
    assert f'name="vat_{p1}_vat_rate" value="10.00"' in list_html
    assert "₺3,100.00" in list_html


def test_scheduler_generates_previous_month_drafts_once(app):
    from app.services.scheduler_service import _generate_monthly_drafts, _previous_month

    party_id = _make_doctor(app, name="Dr. Scheduler")
    _add_work_order(app, party_id, date(2026, 6, 12), 900)

    assert _previous_month(date(2026, 7, 1)) == (2026, 6)

    import app.services.scheduler_service as sched

    class FixedDate(date):
        @classmethod
        def today(cls):
            return date(2026, 7, 1)

    original_date = sched.date
    sched.date = FixedDate
    try:
        _generate_monthly_drafts(app)
        with app.app_context():
            rows = db.session.execute(db.select(Makbuz).where(Makbuz.party_id == party_id)).scalars().all()
            assert len(rows) == 1
            assert rows[0].subtotal == Decimal("900.00")

        # Second call the same day must not duplicate the draft (atomic run-guard).
        _generate_monthly_drafts(app)
        with app.app_context():
            rows = db.session.execute(db.select(Makbuz).where(Makbuz.party_id == party_id)).scalars().all()
            assert len(rows) == 1
    finally:
        sched.date = original_date


def test_scheduler_noop_when_not_first_of_month(app):
    from app.services.scheduler_service import _generate_monthly_drafts

    party_id = _make_doctor(app, name="Dr. Scheduler NoOp")
    _add_work_order(app, party_id, date(2026, 6, 12), 900)

    import app.services.scheduler_service as sched

    class FixedDate(date):
        @classmethod
        def today(cls):
            return date(2026, 7, 15)

    original_date = sched.date
    sched.date = FixedDate
    try:
        _generate_monthly_drafts(app)
        with app.app_context():
            count = db.session.execute(
                db.select(db.func.count(Makbuz.id)).where(Makbuz.party_id == party_id)
            ).scalar_one()
            assert count == 0
    finally:
        sched.date = original_date


def test_makbuz_detail_renders_catalog_item_names_not_raw_json(client, app):
    """apparatus_type/extra_addons store a JSON catalog selection; the page
    must show item names, not the raw JSON (regression: was displayed as-is)."""
    login(client, "admin", "admin-pass")
    party_id = _make_doctor(app, name="Fatma Aydın")
    apparatus = json.dumps([{"id": 31, "name": "Activator (FKO)", "price": 2500, "currency": "TL"}])
    extra = json.dumps([{"id": 49, "name": "Lingual Sheat", "price": 4, "currency": "USD"}])
    with app.app_context():
        db.session.add(WorkOrder(
            party_id=party_id, work_date=date(2026, 7, 20), apparatus_type=apparatus,
            extra_addons=extra, patient_name="Fatma Aydın",
            apparatus_price=2500, extra_price=Decimal("188.57"), total_price=Decimal("2688.57"),
        ))
        db.session.commit()

    response = client.get(f"/makbuzlar/{party_id}?year=2026&month=7")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert '[{"id"' not in html
    assert "Activator (FKO)" in html
    assert "Lingual Sheat" in html

    response = client.get("/")
    html = response.get_data(as_text=True)
    assert '[{"id"' not in html
    assert "Activator (FKO)" in html


def test_format_items_parses_catalog_json_and_falls_back_to_plain_text():
    from app.services.makbuz_pdf_service import _format_items

    catalog_json = json.dumps([{"id": 31, "name": "Activator (FKO)", "price": 2500, "currency": "TL"}])
    assert _format_items(catalog_json) == "Activator (FKO) (₺2,500.00)"

    multi_json = json.dumps([
        {"id": 1, "name": "A", "price": 10, "currency": "USD"},
        {"id": 2, "name": "B", "price": 20, "currency": "TL"},
    ])
    assert _format_items(multi_json) == "A ($10.00), B (₺20.00)"

    assert _format_items("Lingual Ark") == "Lingual Ark"
    assert _format_items(None) == ""
    assert _format_items("") == ""


def test_makbuz_pdf_generation_does_not_crash_with_catalog_json(app):
    from app.services.makbuz_pdf_service import generate_makbuz_pdf

    party_id = _make_doctor(app, name="Fatma Aydın PDF")
    apparatus = json.dumps([{"id": 31, "name": "Activator (FKO)", "price": 2500, "currency": "TL"}])
    with app.app_context():
        wo = WorkOrder(
            party_id=party_id, work_date=date(2026, 7, 20), apparatus_type=apparatus,
            patient_name="Fatma Aydın", apparatus_price=2500, extra_price=0, total_price=2500,
        )
        db.session.add(wo)
        makbuz = Makbuz(
            party_id=party_id, year=2026, month=7, work_order_count=1,
            subtotal=Decimal("2500.00"), generated_at=datetime.now(),
        )
        makbuz.recalculate_totals()
        db.session.add(makbuz)
        db.session.commit()

        pdf_bytes = generate_makbuz_pdf(makbuz, [wo])
        assert pdf_bytes[:4] == b"%PDF"
        assert len(pdf_bytes) > 1000
