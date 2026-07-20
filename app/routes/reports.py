from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from flask import Blueprint, render_template, request
from flask_login import login_required
from app.authz import permissions_required
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models.models import (
    ExchangeRate,
    INVOICE_CATEGORY_LABELS,
    Invoice,
    InvoiceItem,
    InvoiceItemType,
    Party,
    PartyType,
    Payment,
    invoice_item_category_key,
)
from app.services.validation_service import parse_date


reports_bp = Blueprint("reports", __name__)


STATUS_LABELS = {
    Invoice.STATUS_PENDING: "Bekliyor",
    Invoice.STATUS_PAID: "Ödendi",
    Invoice.STATUS_OVERDUE: "Gecikmiş",
    Invoice.STATUS_CANCELLED: "İptal",
}
PATIENT_STATUS_LABELS = {
    "active": "Aktif tedavi",
    "completed": "Tamamlandı",
    "planned": "Planlandı",
    "on_hold": "Beklemede",
    "inactive": "Pasif",
}


def _resolve_period(today: date) -> tuple[date, date, str]:
    period = request.args.get("period", "this_month")
    explicit_start = parse_date(request.args.get("start_date", ""))
    explicit_end = parse_date(request.args.get("end_date", ""))

    if period == "custom" and (explicit_start or explicit_end):
        start = explicit_start or today.replace(month=1, day=1)
        end = explicit_end or today
        period = "custom"
    elif period == "last_30":
        start, end = today - timedelta(days=29), today
    elif period == "this_year":
        start, end = today.replace(month=1, day=1), today
    elif period == "last_year":
        start = today.replace(year=today.year - 1, month=1, day=1)
        end = today.replace(year=today.year - 1, month=12, day=31)
    else:
        period = "this_month"
        start, end = today.replace(day=1), today

    if start > end:
        start, end = end, start
    return start, end, period


def _trend_rows(start: date, end: date, invoices: list[Invoice], payments: list[Payment]) -> list[dict]:
    day_span = (end - start).days + 1
    use_months = day_span > 100
    values: dict[tuple[int, int] | date, dict[str, Decimal]] = defaultdict(
        lambda: {"issued": Decimal("0.00"), "collected": Decimal("0.00")}
    )

    def key_for(value: date):
        if use_months:
            return value.year, value.month
        return value - timedelta(days=value.weekday())

    for invoice in invoices:
        values[key_for(invoice.invoice_date)]["issued"] += invoice.total_eur
    for payment in payments:
        values[key_for(payment.payment_date)]["collected"] += payment.amount_eur

    rows = []
    for key in sorted(values):
        if use_months:
            label = f"{key[1]:02d}.{key[0]}"
        else:
            label = key.strftime("%d.%m")
        rows.append({"label": label, **values[key]})

    return rows[-12:]


@reports_bp.route("/")
@login_required
@permissions_required("reports.view")
def index():
    today = date.today()
    start_date, end_date, selected_period = _resolve_period(today)

    invoices = db.session.execute(
        db.select(Invoice)
        .options(selectinload(Invoice.items).selectinload(InvoiceItem.treatment))
        .where(
            Invoice.invoice_date.between(start_date, end_date),
            Invoice.is_deleted == False,
            Invoice.status != Invoice.STATUS_CANCELLED,
        )
        .order_by(Invoice.invoice_date)
    ).scalars().all()

    payments = db.session.execute(
        db.select(Payment)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .where(
            Payment.payment_date.between(start_date, end_date),
            Invoice.is_deleted == False,
            Invoice.status != Invoice.STATUS_CANCELLED,
        )
        .order_by(Payment.payment_date)
    ).scalars().all()

    # Receivables are a point-in-time balance at the report end date. Include
    # invoices from before the selected period and ignore later payments.
    receivable_invoices = db.session.execute(
        db.select(Invoice)
        .options(selectinload(Invoice.payments))
        .where(
            Invoice.invoice_date <= end_date,
            Invoice.is_deleted == False,
            Invoice.status != Invoice.STATUS_CANCELLED,
        )
        .order_by(Invoice.invoice_date)
    ).scalars().all()

    issued_eur, issued_try = db.session.execute(
        db.select(
            db.func.coalesce(db.func.sum(Invoice.total_eur), 0),
            db.func.coalesce(db.func.sum(Invoice.total_try), 0),
        ).where(
            Invoice.invoice_date.between(start_date, end_date),
            Invoice.is_deleted == False,
            Invoice.status != Invoice.STATUS_CANCELLED,
        )
    ).one()
    collected_eur, collected_try = db.session.execute(
        db.select(
            db.func.coalesce(db.func.sum(Payment.amount_eur), 0),
            db.func.coalesce(db.func.sum(Payment.amount_try), 0),
        ).join(Invoice, Payment.invoice_id == Invoice.id).where(
            Payment.payment_date.between(start_date, end_date),
            Invoice.is_deleted == False,
            Invoice.status != Invoice.STATUS_CANCELLED,
        )
    ).one()

    outstanding_eur = Decimal("0.00")
    outstanding_try = Decimal("0.00")
    overdue_eur = Decimal("0.00")
    aging = {
        "not_due": {"label": "Vadesi gelmedi", "count": 0, "amount": Decimal("0.00")},
        "days_0_30": {"label": "0-30 gün", "count": 0, "amount": Decimal("0.00")},
        "days_31_60": {"label": "31-60 gün", "count": 0, "amount": Decimal("0.00")},
        "days_61_plus": {"label": "61+ gün", "count": 0, "amount": Decimal("0.00")},
    }
    receivable_count = 0
    for invoice in receivable_invoices:
        paid_eur = sum(
            payment.amount_eur
            for payment in invoice.payments
            if payment.payment_date <= end_date
        )
        remaining_eur = max(invoice.total_eur - paid_eur, Decimal("0.00"))
        if remaining_eur <= Decimal("0.01"):
            continue
        receivable_count += 1

        # Preserve the invoice's fixed exchange-rate basis for book-value TRY.
        # Payment-date TRY values cannot be subtracted without mixing rates.
        remaining_ratio = remaining_eur / invoice.total_eur if invoice.total_eur else Decimal("0")
        remaining_try = max(invoice.total_try * remaining_ratio, Decimal("0.00"))
        outstanding_eur += remaining_eur
        outstanding_try += remaining_try
        due_reference = invoice.due_date or invoice.invoice_date
        age_days = (end_date - due_reference).days
        if age_days < 0:
            bucket = "not_due"
        elif age_days <= 30:
            bucket = "days_0_30"
        elif age_days <= 60:
            bucket = "days_31_60"
        else:
            bucket = "days_61_plus"
        aging[bucket]["count"] += 1
        aging[bucket]["amount"] += remaining_eur
        if age_days > 0:
            overdue_eur += remaining_eur

    treatment_totals: dict[int, dict] = {}
    category_totals: dict[str, dict] = defaultdict(lambda: {"count": 0, "amount_eur": Decimal("0.00")})
    for invoice in invoices:
        for item in invoice.items:
            item_type = item.item_type.value if isinstance(item.item_type, InvoiceItemType) else str(item.item_type)
            category_key = invoice_item_category_key(item)
            quantity = int(item.quantity or 0)
            amount_eur = item.line_total_eur + item.vat_amount_eur
            category_totals[category_key]["count"] += quantity
            category_totals[category_key]["amount_eur"] += amount_eur
            if item_type == InvoiceItemType.TREATMENT.value and item.treatment:
                row = treatment_totals.setdefault(item.treatment.id, {
                    "name": item.treatment.name,
                    "category": item.treatment.category,
                    "count": 0,
                    "amount_eur": Decimal("0.00"),
                })
                row["count"] += quantity
                row["amount_eur"] += amount_eur

    treatment_stats = sorted(
        treatment_totals.values(), key=lambda row: (row["count"], row["amount_eur"]), reverse=True
    )[:8]
    category_stats = [
        {"category": key, **value}
        for key, value in sorted(
            category_totals.items(), key=lambda pair: pair[1]["amount_eur"], reverse=True
        )
    ]

    status_counts = defaultdict(int)
    for invoice in invoices:
        status_counts[invoice.status] += 1
    invoice_statuses = [
        {"status": status, "label": STATUS_LABELS[status], "count": status_counts.get(status, 0)}
        for status in (Invoice.STATUS_PAID, Invoice.STATUS_PENDING, Invoice.STATUS_OVERDUE)
    ]

    patient_status_rows = db.session.execute(
        db.select(Party.treatment_status, db.func.count(Party.id).label("count"))
        .where(Party.party_type == PartyType.PATIENT, Party.is_active == True)
        .group_by(Party.treatment_status)
    ).all()
    patient_stats = [
        {
            "status": row.treatment_status or "active",
            "label": PATIENT_STATUS_LABELS.get(row.treatment_status or "active", row.treatment_status or "active"),
            "count": row.count,
        }
        for row in patient_status_rows
    ]

    exchange_rates = db.session.execute(
        db.select(ExchangeRate)
        .where(ExchangeRate.rate_date <= end_date)
        .order_by(ExchangeRate.rate_date.desc())
        .limit(12)
    ).scalars().all()
    current_rate = exchange_rates[0] if exchange_rates else None
    previous_rate = exchange_rates[1] if len(exchange_rates) > 1 else None
    rate_delta = (
        current_rate.eur_to_try - previous_rate.eur_to_try
        if current_rate and previous_rate else None
    )

    trend_rows = _trend_rows(start_date, end_date, invoices, payments)
    max_trend_value = max(
        (max(row["issued"], row["collected"]) for row in trend_rows), default=Decimal("1")
    ) or Decimal("1")
    max_category_amount = max((row["amount_eur"] for row in category_stats), default=Decimal("1")) or Decimal("1")
    max_aging_amount = max((row["amount"] for row in aging.values()), default=Decimal("1")) or Decimal("1")

    return render_template(
        "reports/index.html",
        today=today,
        start_date=start_date,
        end_date=end_date,
        selected_period=selected_period,
        issued_eur=issued_eur,
        issued_try=issued_try,
        collected_eur=collected_eur,
        collected_try=collected_try,
        outstanding_eur=outstanding_eur,
        outstanding_try=outstanding_try,
        receivable_count=receivable_count,
        overdue_eur=overdue_eur,
        collection_ratio=(collected_eur / issued_eur * 100) if issued_eur else 0,
        invoice_count=len(invoices),
        payment_count=len(payments),
        treatment_stats=treatment_stats,
        category_stats=category_stats,
        category_labels=INVOICE_CATEGORY_LABELS,
        invoice_statuses=invoice_statuses,
        patient_stats=patient_stats,
        aging_rows=list(aging.values()),
        exchange_rates=exchange_rates,
        current_rate=current_rate,
        rate_delta=rate_delta,
        trend_rows=trend_rows,
        max_trend_value=max_trend_value,
        max_category_amount=max_category_amount,
        max_aging_amount=max_aging_amount,
    )
