from flask import Blueprint, render_template
from flask_login import login_required
from datetime import date, timedelta

from app.extensions import db
from app.models.models import Party, PartyType, Treatment, ExchangeRate, WorkOrder
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

    total_treatments = db.session.execute(
        db.select(db.func.count(Treatment.id)).where(Treatment.is_active == True)
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

    total_work_orders_all = db.session.execute(
        db.select(db.func.count(WorkOrder.id))
    ).scalar() or 0

    recent_work_orders = db.session.execute(
        db.select(WorkOrder)
        .join(Party, WorkOrder.party_id == Party.id)
        .order_by(WorkOrder.created_at.desc())
        .limit(5)
    ).scalars().all()

    recent_patients = db.session.execute(
        db.select(Party)
        .where(Party.party_type == PartyType.DENTIST, Party.is_active == True)
        .order_by(Party.created_at.desc())
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
        total_treatments=total_treatments,
        monthly_work_orders=monthly_work_orders,
        monthly_total_eur=monthly_total_eur,
        total_work_orders_all=total_work_orders_all,
        recent_work_orders=recent_work_orders,
        recent_patients=recent_patients,
        current_rate=current_rate,
        current_usd_rate=current_rate.usd_to_try if current_rate else None,
    )
