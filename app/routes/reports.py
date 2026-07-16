from flask import Blueprint, render_template, request
from flask_login import login_required
from datetime import date, timedelta
from sqlalchemy import func

from app.extensions import db
from app.models.models import Invoice, Patient, PatientTreatment, Treatment, TreatmentCategory, ExchangeRate

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/")
@login_required
def index():
    today = date.today()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    # Monthly revenue
    monthly_revenue = db.session.execute(
        db.select(
            func.sum(Invoice.total_eur).label("total_eur"),
            func.sum(Invoice.total_try).label("total_try"),
        ).where(
            Invoice.invoice_date >= month_start,
            Invoice.is_deleted == False,
            Invoice.status == Invoice.STATUS_PAID,
        )
    ).one()

    # Yearly revenue
    yearly_revenue = db.session.execute(
        db.select(
            func.sum(Invoice.total_eur).label("total_eur"),
            func.sum(Invoice.total_try).label("total_try"),
        ).where(
            Invoice.invoice_date >= year_start,
            Invoice.is_deleted == False,
            Invoice.status == Invoice.STATUS_PAID,
        )
    ).one()

    # Pending amounts
    pending_amounts = db.session.execute(
        db.select(
            func.sum(Invoice.total_eur).label("total_eur"),
            func.sum(Invoice.total_try).label("total_try"),
            func.count(Invoice.id).label("count"),
        ).where(
            Invoice.status == Invoice.STATUS_PENDING,
            Invoice.is_deleted == False,
        )
    ).one()

    # Treatment statistics
    treatment_stats = db.session.execute(
        db.select(
            Treatment.name,
            Treatment.category,
            func.count(PatientTreatment.id).label("count"),
        )
        .join(PatientTreatment, PatientTreatment.treatment_id == Treatment.id)
        .group_by(Treatment.id)
        .order_by(func.count(PatientTreatment.id).desc())
        .limit(10)
    ).all()

    # Category statistics
    category_stats = db.session.execute(
        db.select(
            Treatment.category,
            func.count(PatientTreatment.id).label("count"),
        )
        .join(PatientTreatment, PatientTreatment.treatment_id == Treatment.id)
        .group_by(Treatment.category)
        .order_by(func.count(PatientTreatment.id).desc())
    ).all()

    category_labels = {
        "orthodontic": "Ortodonti",
        "prosthetic": "Protetik",
        "surgical": "Cerrahi",
        "preventive": "Koruyucu",
        "restorative": "Restoratif",
        "periodontic": "Perio/Endo",
        "implant": "İmplant",
        "cosmetic": "Kozmetik",
        "other": "Diğer",
    }

    # Patient count by status
    patient_stats = db.session.execute(
        db.select(
            Patient.treatment_status,
            func.count(Patient.id).label("count"),
        )
        .where(Patient.is_active == True)
        .group_by(Patient.treatment_status)
    ).all()

    # Exchange rate history
    exchange_rates = db.session.execute(
        db.select(ExchangeRate)
        .order_by(ExchangeRate.rate_date.desc())
        .limit(30)
    ).scalars().all()

    return render_template(
        "reports/index.html",
        monthly_revenue=monthly_revenue,
        yearly_revenue=yearly_revenue,
        pending_amounts=pending_amounts,
        treatment_stats=treatment_stats,
        category_stats=category_stats,
        category_labels=category_labels,
        patient_stats=patient_stats,
        exchange_rates=exchange_rates,
        today=today,
        month_start=month_start,
        year_start=year_start,
    )
