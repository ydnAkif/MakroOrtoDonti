from flask import Blueprint, render_template
from flask_login import login_required
from datetime import date

from app.extensions import db
from app.models.models import Party, PartyType, ExchangeRate, WorkOrder, Makbuz
from sqlalchemy import extract

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    total_patients = db.session.execute(
        db.select(db.func.count(Party.id)).where(
            Party.party_type == PartyType.DENTIST,
            Party.is_active == True
        )
    ).scalar() or 0

    today = date.today()
    current_month = today.month
    current_year = today.year

    monthly_work_orders = db.session.execute(
        db.select(db.func.count(WorkOrder.id)).where(
            extract("year", WorkOrder.work_date) == current_year,
            extract("month", WorkOrder.work_date) == current_month,
        )
    ).scalar() or 0

    monthly_total_eur = db.session.execute(
        db.select(db.func.coalesce(db.func.sum(WorkOrder.total_price), 0)).where(
            extract("year", WorkOrder.work_date) == current_year,
            extract("month", WorkOrder.work_date) == current_month,
        )
    ).scalar() or 0

    monthly_drafts = db.session.execute(
        db.select(db.func.count(Makbuz.id)).where(
            Makbuz.year == current_year,
            Makbuz.month == current_month,
            Makbuz.status == Makbuz.STATUS_DRAFT,
        )
    ).scalar() or 0
    awaiting_payment = db.session.execute(
        db.select(db.func.count(Makbuz.id)).where(Makbuz.status == Makbuz.STATUS_SENT)
    ).scalar() or 0

    recent_work_orders = db.session.execute(
        db.select(WorkOrder)
        .join(Party, WorkOrder.party_id == Party.id)
        .order_by(WorkOrder.created_at.desc())
        .limit(5)
    ).scalars().all()

    current_rate = db.session.execute(
        db.select(ExchangeRate)
        .order_by(ExchangeRate.rate_date.desc())
        .limit(1)
    ).scalar_one_or_none()

    return render_template(
        "dashboard/index.html",
        total_patients=total_patients,
        monthly_work_orders=monthly_work_orders,
        monthly_total_eur=monthly_total_eur,
        monthly_drafts=monthly_drafts,
        awaiting_payment=awaiting_payment,
        recent_work_orders=recent_work_orders,
        current_rate=current_rate,
        current_usd_rate=current_rate.usd_to_try if current_rate else None,
    )
