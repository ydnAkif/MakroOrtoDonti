from flask import Blueprint, render_template, request
from flask_login import login_required
from datetime import date, timedelta
from sqlalchemy import func

from app.extensions import db
from app.models.models import Invoice, Patient, PatientTreatment, Treatment, TreatmentCategory, ExchangeRate, Party, PartyType, InvoiceItem

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

    # Treatment statistics (counts from InvoiceItem + PatientTreatment)
    inv_counts = db.session.execute(
        db.select(
            InvoiceItem.treatment_id,
            func.sum(InvoiceItem.quantity).label("qty")
        )
        .where(InvoiceItem.item_type == "treatment", InvoiceItem.treatment_id.isnot(None))
        .group_by(InvoiceItem.treatment_id)
    ).all()

    pt_counts = db.session.execute(
        db.select(
            PatientTreatment.treatment_id,
            func.count(PatientTreatment.id).label("qty")
        )
        .where(PatientTreatment.treatment_id.isnot(None))
        .group_by(PatientTreatment.treatment_id)
    ).all()

    totals_by_id = {}
    for tid, qty in inv_counts:
        if tid:
            totals_by_id[tid] = totals_by_id.get(tid, 0) + int(qty or 0)
    for tid, qty in pt_counts:
        if tid:
            totals_by_id[tid] = totals_by_id.get(tid, 0) + int(qty or 0)

    treatments_list = []
    if totals_by_id:
        treatments_in_db = db.session.execute(
            db.select(Treatment).where(Treatment.id.in_(totals_by_id.keys()))
        ).scalars().all()
        
        for t in treatments_in_db:
            treatments_list.append({
                "id": t.id,
                "name": t.name,
                "category": t.category,
                "count": totals_by_id.get(t.id, 0)
            })
        
        treatments_list.sort(key=lambda x: x["count"], reverse=True)
    else:
        all_treatments = db.session.execute(
            db.select(Treatment).order_by(Treatment.name).limit(10)
        ).scalars().all()
        treatments_list = [{
            "id": t.id,
            "name": t.name,
            "category": t.category,
            "count": 0
        } for t in all_treatments]

    treatment_stats = treatments_list[:10]

    # Category statistics
    category_counts = {}
    for item in treatments_list:
        cat = item["category"] or "other"
        category_counts[cat] = category_counts.get(cat, 0) + item["count"]

    category_stats = [
        {"category": cat, "count": count}
        for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    category_labels = {
        "orthodontic": "Ortodonti",
        "prosthetic": "Protetik",
        "surgical": "Cerrahi",
        "preventive": "Koruyucu",
        "restorative": "Restoratif",
        "periodontic": "Periodontoloji (Diş Eti)",
        "endodontic": "Endodonti (Kanal Tedavisi)",
        "implant": "İmplant",
        "cosmetic": "Kozmetik",
        "other": "Diğer",
    }

    # Patient count by status
    patient_stats = db.session.execute(
        db.select(
            Party.treatment_status,
            func.count(Party.id).label("count"),
        )
        .where(Party.party_type == PartyType.PATIENT, Party.is_active == True)
        .group_by(Party.treatment_status)
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
