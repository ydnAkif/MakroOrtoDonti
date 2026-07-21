from __future__ import annotations

from datetime import date
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


def test_bulk_approve_and_send(client, app):
    login(client, "admin", "admin-pass")
    p1 = _make_doctor(app, name="Dr. Bulk One", phone="+905551110001")
    p2 = _make_doctor(app, name="Dr. Bulk Two", phone="+905551110002")
    _add_work_order(app, p1, date(2026, 6, 3), 1000)
    _add_work_order(app, p2, date(2026, 6, 4), 2000)

    with patch("app.services.whatsapp_service.WhatsAppService.send_makbuz_message", return_value={"success": True, "message": "ok"}):
        response = client.post(
            "/makbuzlar/bulk-send",
            data={
                "year": 2026, "month": 6,
                "party_ids": [str(p1), str(p2)],
                f"vat_{p1}_vat_applied": "on",
                f"vat_{p1}_vat_rate": "10",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    with app.app_context():
        m1 = db.session.execute(db.select(Makbuz).where(Makbuz.party_id == p1)).scalar_one()
        m2 = db.session.execute(db.select(Makbuz).where(Makbuz.party_id == p2)).scalar_one()
        assert m1.status == Makbuz.STATUS_SENT
        assert m1.vat_applied is True
        assert m1.grand_total == Decimal("1100.00")
        assert m2.status == Makbuz.STATUS_SENT
        assert m2.vat_applied is False


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
