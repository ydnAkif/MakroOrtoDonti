from flask import Blueprint, render_template
from flask_login import login_required
from datetime import date, timedelta

from app.extensions import db
from app.models.models import Patient, Invoice, Treatment, ExchangeRate, InvoiceItem

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    total_patients = db.session.execute(
        db.select(db.func.count(Patient.id)).where(Patient.is_active == True)
    ).scalar() or 0

    total_treatments = db.session.execute(
        db.select(db.func.count(Treatment.id)).where(Treatment.is_active == True)
    ).scalar() or 0

    pending_invoices = db.session.execute(
        db.select(db.func.count(Invoice.id)).where(
            Invoice.status == Invoice.STATUS_PENDING,
            Invoice.is_deleted == False
        )
    ).scalar() or 0

    total_revenue_eur = db.session.execute(
        db.select(db.func.sum(Invoice.total_eur)).where(
            Invoice.status == Invoice.STATUS_PAID,
            Invoice.is_deleted == False
        )
    ).scalar() or 0

    total_revenue_try = db.session.execute(
        db.select(db.func.sum(Invoice.total_try)).where(
            Invoice.status == Invoice.STATUS_PAID,
            Invoice.is_deleted == False
        )
    ).scalar() or 0

    recent_invoices = db.session.execute(
        db.select(Invoice)
        .where(Invoice.is_deleted == False)
        .order_by(Invoice.created_at.desc())
        .limit(5)
    ).scalars().all()

    recent_patients = db.session.execute(
        db.select(Patient)
        .where(Patient.is_active == True)
        .order_by(Patient.created_at.desc())
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
        pending_invoices=pending_invoices,
        total_revenue_eur=total_revenue_eur,
        total_revenue_try=total_revenue_try,
        recent_invoices=recent_invoices,
        recent_patients=recent_patients,
        current_rate=current_rate,
    )
