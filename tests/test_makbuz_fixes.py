from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import pytest

from app.extensions import db
from app.models.models import Party, PartyType, Makbuz, WorkOrder
from conftest import login


def _make_doctor(app, name="Dr. Fix Test", phone="+905559990033"):
    with app.app_context():
        party = Party(party_type=PartyType.DENTIST, name=name, phone=phone)
        db.session.add(party)
        db.session.commit()
        return party.id


def test_send_makbuz_preserves_paid_status(app, monkeypatch):
    from app.services.makbuz_send_queue import send_makbuz_via_whatsapp
    from app.services.whatsapp_service import WhatsAppService

    # Mock WhatsAppService.send_makbuz_message to avoid actual WhatsApp API call
    monkeypatch.setattr(
        WhatsAppService,
        "send_makbuz_message",
        lambda makbuz, pdf_bytes: {"success": True, "message": "Gönderildi"}
    )

    party_id = _make_doctor(app)
    with app.app_context():
        makbuz = Makbuz(
            party_id=party_id,
            year=2026,
            month=6,
            work_order_count=1,
            subtotal=Decimal("100.00"),
            vat_applied=False,
            vat_rate=Decimal("0.00"),
            status=Makbuz.STATUS_PAID,
            paid_at=date(2026, 6, 20),
            paid_amount=Decimal("100.00"),
            generated_at=datetime.now().astimezone(),
        )
        makbuz.recalculate_totals()
        db.session.add(makbuz)
        db.session.commit()
        makbuz_id = makbuz.id

    with app.app_context():
        ok, msg = send_makbuz_via_whatsapp(makbuz_id)
        assert ok is True
        
        m = db.session.get(Makbuz, makbuz_id)
        assert m.status == Makbuz.STATUS_PAID  # Must remain PAID!
        assert m.sent_at is not None


def test_unmark_paid_status_logic(client, app):
    login(client, "admin", "admin-pass")
    party_id = _make_doctor(app)

    # Scenario 1: Makbuz with sent_at (sent before being paid)
    with app.app_context():
        m1 = Makbuz(
            party_id=party_id,
            year=2026,
            month=5,
            work_order_count=1,
            subtotal=Decimal("200.00"),
            status=Makbuz.STATUS_PAID,
            sent_at=datetime.now().astimezone(),
            paid_at=date(2026, 5, 10),
            paid_amount=Decimal("200.00"),
            generated_at=datetime.now().astimezone(),
        )
        m1.recalculate_totals()
        db.session.add(m1)
        
        # Scenario 2: Makbuz without sent_at (paid directly from draft)
        m2 = Makbuz(
            party_id=party_id,
            year=2026,
            month=4,
            work_order_count=1,
            subtotal=Decimal("300.00"),
            status=Makbuz.STATUS_PAID,
            sent_at=None,
            paid_at=date(2026, 4, 10),
            paid_amount=Decimal("300.00"),
            generated_at=datetime.now().astimezone(),
        )
        m2.recalculate_totals()
        db.session.add(m2)
        db.session.commit()
        m1_id, m2_id = m1.id, m2.id

    # Unmark m1
    res1 = client.post(f"/payments/{m1_id}/unmark-paid", follow_redirects=True)
    assert res1.status_code == 200

    # Unmark m2
    res2 = client.post(f"/payments/{m2_id}/unmark-paid", follow_redirects=True)
    assert res2.status_code == 200

    with app.app_context():
        m1_db = db.session.get(Makbuz, m1_id)
        assert m1_db.status == Makbuz.STATUS_SENT  # Has sent_at, reverts to SENT

        m2_db = db.session.get(Makbuz, m2_id)
        assert m2_db.status == Makbuz.STATUS_DRAFT  # No sent_at, reverts to DRAFT


def test_list_makbuzlar_includes_orphan_makbuz(client, app):
    login(client, "admin", "admin-pass")
    party_id = _make_doctor(app, name="Dr. Orphan Test")

    # Create a Makbuz with 0 WorkOrders in DB
    with app.app_context():
        makbuz = Makbuz(
            party_id=party_id,
            year=2026,
            month=3,
            work_order_count=1,
            subtotal=Decimal("500.00"),
            status=Makbuz.STATUS_SENT,
            generated_at=datetime.now().astimezone(),
        )
        makbuz.recalculate_totals()
        db.session.add(makbuz)
        db.session.commit()

    response = client.get("/makbuzlar/?year=2026&month=3")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    # Doctor and Makbuz must be present in table
    assert "Dr. Orphan Test" in html
    assert "500.00" in html
