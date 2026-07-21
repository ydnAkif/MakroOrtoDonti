from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
import json
import pytest

from app.extensions import db
from app.models.models import Party, PartyType, WorkOrder, Makbuz, ExchangeRate
from conftest import login


def _make_doctor(app, name="Dr. Report Test", phone="+905559990022"):
    with app.app_context():
        party = Party(party_type=PartyType.DENTIST, name=name, phone=phone)
        db.session.add(party)
        db.session.commit()
        return party.id


def _add_work_order_json(app, party_id, work_date, app_items, ext_items, rate=40.0):
    with app.app_context():
        wo = WorkOrder(
            party_id=party_id,
            work_date=work_date,
            apparatus_type=json.dumps(app_items),
            extra_addons=json.dumps(ext_items),
            patient_name="Report Patient",
            apparatus_price=Decimal(sum(item["price"] for item in app_items)),
            extra_price=Decimal(sum(item["price"] for item in ext_items)),
            total_price=Decimal(sum(item["price"] for item in app_items) + sum(item["price"] for item in ext_items)),
            exchange_rate_applied=Decimal(rate),
        )
        db.session.add(wo)
        db.session.commit()
        return wo.id


def _create_makbuz(app, party_id, year, month, status=Makbuz.STATUS_SENT, paid_at=None, paid_amount=None):
    with app.app_context():
        makbuz = Makbuz(
            party_id=party_id,
            year=year,
            month=month,
            work_order_count=1,
            subtotal=Decimal("200.00"),
            vat_applied=True,
            vat_rate=Decimal("10.00"),
            status=status,
            generated_at=datetime.now().astimezone(),
            paid_at=paid_at,
            paid_amount=paid_amount,
        )
        makbuz.recalculate_totals()
        db.session.add(makbuz)
        db.session.commit()
        return makbuz.id


def test_reports_new_data_sent_makbuz(client, app):
    login(client, "admin", "admin-pass")
    party_id = _make_doctor(app)
    
    # Work order and sent makbuz in current month
    today = date.today()
    _add_work_order_json(
        app, party_id, today,
        app_items=[{"name": "Hawley Retainer", "price": 100.0, "currency": "TL"}],
        ext_items=[{"name": "Screw", "price": 10.0, "currency": "TL"}]
    )
    _create_makbuz(app, party_id, today.year, today.month, status=Makbuz.STATUS_SENT)

    response = client.get("/reports/?period=this_month")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # The treatment names should appear in stats
    assert "Hawley Retainer" in html
    assert "Screw" in html
    
    # Billed TRY should be in HTML
    # subtotal = 200, vat = 10%, grand_total = 220
    assert "220.00" in html


def test_reports_new_data_paid_makbuz(client, app):
    login(client, "admin", "admin-pass")
    party_id = _make_doctor(app)
    
    today = date.today()
    _add_work_order_json(
        app, party_id, today,
        app_items=[{"name": "Activator", "price": 200.0, "currency": "EUR"}], # priced in EUR
        ext_items=[]
    )
    _create_makbuz(
        app, party_id, today.year, today.month,
        status=Makbuz.STATUS_PAID,
        paid_at=today,
        paid_amount=Decimal("220.00")
    )

    response = client.get("/reports/?period=this_month")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    assert "Activator" in html
    # Collected should reflect the paid amount
    assert "220.00" in html


def test_reports_aging_new_makbuz(client, app):
    login(client, "admin", "admin-pass")
    party_id = _make_doctor(app)
    
    # Create an old makbuz (e.g. 2 months ago) that is sent but unpaid
    today = date.today()
    two_months_ago = today - timedelta(days=60)
    
    _add_work_order_json(
        app, party_id, two_months_ago,
        app_items=[{"name": "RPE", "price": 300.0, "currency": "TL"}],
        ext_items=[]
    )
    _create_makbuz(app, party_id, two_months_ago.year, two_months_ago.month, status=Makbuz.STATUS_SENT)

    response = client.get("/reports/?period=this_year")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    assert "RPE" in html


def test_reports_different_periods_and_usd(client, app):
    login(client, "admin", "admin-pass")
    party_id = _make_doctor(app)
    
    today = date.today()
    # Work order with USD price
    _add_work_order_json(
        app, party_id, today,
        app_items=[{"name": "USD Apparatus", "price": 50.0, "currency": "USD"}],
        ext_items=[{"name": "Custom Ext", "price": 10.0, "currency": "TL"}]
    )
    _create_makbuz(app, party_id, today.year, today.month, status=Makbuz.STATUS_SENT)

    # Fetch last_30
    response = client.get("/reports/?period=last_30")
    assert response.status_code == 200
    
    # Fetch this_year
    response = client.get("/reports/?period=this_year")
    assert response.status_code == 200
    
    # Fetch last_year
    response = client.get("/reports/?period=last_year")
    assert response.status_code == 200

    # Fetch custom period
    start_str = (today - timedelta(days=5)).isoformat()
    end_str = today.isoformat()
    response = client.get(f"/reports/?period=custom&start_date={start_str}&end_date={end_str}")
    assert response.status_code == 200
