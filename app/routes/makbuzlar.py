from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models.models import WorkOrder, Party, PartyType, ExchangeRate
from app.authz import permissions_required
from sqlalchemy import func, extract
from app.services.validation_service import parse_date

makbuzlar_bp = Blueprint("makbuzlar", __name__)


@makbuzlar_bp.route("/")
@login_required
@permissions_required("billing.view")
def list_makbuzlar():
    year = request.args.get("year", date.today().year, type=int)
    month = request.args.get("month", date.today().month, type=int)

    work_orders = db.session.execute(
        db.select(WorkOrder)
        .join(Party, WorkOrder.party_id == Party.id)
        .where(
            extract("year", WorkOrder.work_date) == year,
            extract("month", WorkOrder.work_date) == month,
            Party.is_active == True,
        )
    ).scalars().all()

    doctor_data = {}
    for wo in work_orders:
        pid = wo.party_id
        if pid not in doctor_data:
            doctor_data[pid] = {
                "party": wo.party,
                "party_id": pid,
                "count": 0,
                "total_apparatus": Decimal("0.00"),
                "total_extra": Decimal("0.00"),
                "total_price": Decimal("0.00"),
            }
        d = doctor_data[pid]
        d["count"] += 1
        d["total_apparatus"] += wo.apparatus_price
        d["total_extra"] += wo.extra_price
        d["total_price"] += wo.total_price

    doctors = sorted(doctor_data.values(), key=lambda x: x["total_price"], reverse=True)

    grand_total_apparatus = sum(d["total_apparatus"] for d in doctors)
    grand_total_extra = sum(d["total_extra"] for d in doctors)
    grand_total_price = sum(d["total_price"] for d in doctors)
    grand_total_count = sum(d["count"] for d in doctors)

    months = [
        (1, "Ocak"), (2, "Şubat"), (3, "Mart"), (4, "Nisan"),
        (5, "Mayıs"), (6, "Haziran"), (7, "Temmuz"), (8, "Ağustos"),
        (9, "Eylül"), (10, "Ekim"), (11, "Kasım"), (12, "Aralık"),
    ]

    return render_template(
        "makbuzlar/list.html",
        doctors=doctors,
        year=year,
        month=month,
        months=months,
        grand_total_apparatus=grand_total_apparatus,
        grand_total_extra=grand_total_extra,
        grand_total_price=grand_total_price,
        grand_total_count=grand_total_count,
    )


@makbuzlar_bp.route("/<int:party_id>")
@login_required
@permissions_required("billing.view")
def detail_makbuz(party_id):
    party = db.get_or_404(Party, party_id)
    year = request.args.get("year", date.today().year, type=int)
    month = request.args.get("month", date.today().month, type=int)

    work_orders = db.session.execute(
        db.select(WorkOrder)
        .where(
            WorkOrder.party_id == party_id,
            extract("year", WorkOrder.work_date) == year,
            extract("month", WorkOrder.work_date) == month,
        )
        .order_by(WorkOrder.work_date.desc())
    ).scalars().all()

    total_apparatus = sum(wo.apparatus_price for wo in work_orders)
    total_extra = sum(wo.extra_price for wo in work_orders)
    total_price = sum(wo.total_price for wo in work_orders)

    months = [
        (1, "Ocak"), (2, "Şubat"), (3, "Mart"), (4, "Nisan"),
        (5, "Mayıs"), (6, "Haziran"), (7, "Temmuz"), (8, "Ağustos"),
        (9, "Eylül"), (10, "Ekim"), (11, "Kasım"), (12, "Aralık"),
    ]

    return render_template(
        "makbuzlar/detail.html",
        party=party,
        work_orders=work_orders,
        year=year,
        month=month,
        months=months,
        total_apparatus=total_apparatus,
        total_extra=total_extra,
        total_price=total_price,
    )


@makbuzlar_bp.route("/api/exchange-rate")
@login_required
@permissions_required("billing.edit")
def get_exchange_rate_for_date():
    """Return the EUR/TRY rate for the requested date."""
    target_date = parse_date(request.args.get("date", ""))
    if not target_date:
        return jsonify({"error": "Geçersiz tarih"}), 400

    rate = db.session.execute(
        db.select(ExchangeRate)
        .where(ExchangeRate.rate_date <= target_date)
        .order_by(ExchangeRate.rate_date.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not rate:
        return jsonify({"error": "Bu tarih için kur bulunamadı"}), 404

    return jsonify({
        "rate": float(rate.eur_to_try),
        "rate_date": rate.rate_date.isoformat(),
        "display_date": rate.rate_date.strftime("%d.%m.%Y"),
        "source": rate.source,
    })
