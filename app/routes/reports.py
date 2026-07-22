from collections import defaultdict
from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal

from flask import Blueprint, render_template, request
from flask_login import login_required
from app.authz import permissions_required
from sqlalchemy import extract
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models.models import (
    ExchangeRate,
    INVOICE_CATEGORY_LABELS,
    Invoice,
    InvoiceItem,
    InvoiceItemType,
    Payment,
    WorkOrder,
    Makbuz,
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


def _trend_rows(start: date, end: date, invoices: Sequence[Invoice], payments: Sequence[Payment], work_orders: Sequence[WorkOrder], makbuz_collections: list[tuple[date, Decimal]]) -> list[dict]:
    day_span = (end - start).days + 1
    use_months = day_span > 100
    values: dict[tuple[int, int] | date, dict[str, Decimal]] = defaultdict(
        lambda: {"issued": Decimal("0.00"), "collected": Decimal("0.00")}
    )

    def key_for(value: date):
        if use_months:
            return value.year, value.month
        return value - timedelta(days=value.weekday())

    # Legacy invoices
    for invoice in invoices:
        values[key_for(invoice.invoice_date)]["issued"] += invoice.total_eur
    # Legacy payments
    for payment in payments:
        values[key_for(payment.payment_date)]["collected"] += payment.amount_eur

    from app.services.exchange_service import get_rate_for_date

    # Work orders (issued)
    for wo in work_orders:
        rate = wo.exchange_rate_applied or Decimal("1")
        if not rate or rate <= 0:
            rate_obj = get_rate_for_date(wo.work_date)
            rate = rate_obj.eur_to_try if rate_obj else Decimal("1")
        if not rate or rate <= 0:
            rate = Decimal("1")
        values[key_for(wo.work_date)]["issued"] += wo.total_price / rate

    # Monthly receipt collection movements, including partial payments.
    for payment_date, amount_try in makbuz_collections:
        rate_obj = get_rate_for_date(payment_date)
        rate = rate_obj.eur_to_try if rate_obj else Decimal("1")
        if not rate or rate <= 0:
            rate = Decimal("1")
        values[key_for(payment_date)]["collected"] += amount_try / rate

    rows = []
    for key in sorted(values):
        if isinstance(key, tuple):
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

    # 1. Fetch Legacy Data
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

    # 2. Fetch New Data
    all_makbuzlar = db.session.execute(
        db.select(Makbuz)
        .order_by(Makbuz.year, Makbuz.month)
    ).scalars().all()

    work_orders_in_period = db.session.execute(
        db.select(WorkOrder)
        .where(WorkOrder.work_date.between(start_date, end_date))
        .order_by(WorkOrder.work_date)
    ).scalars().all()

    # Filter makbuzlar in selected range
    makbuzlar_in_period = []
    for m in all_makbuzlar:
        m_date = date(m.year, m.month, 1)
        if m.month == 12:
            m_next_start = date(m.year + 1, 1, 1)
        else:
            m_next_start = date(m.year, m.month + 1, 1)
        m_end = m_next_start - timedelta(days=1)
        
        if m_date <= end_date and m_end >= start_date:
            makbuzlar_in_period.append(m)

    # 3. Calculate Issued (Billed)
    legacy_issued_eur = sum((inv.total_eur for inv in invoices), Decimal("0.00"))
    legacy_issued_try = sum((inv.total_try for inv in invoices), Decimal("0.00"))

    makbuz_issued_try = Decimal("0.00")
    makbuz_issued_eur = Decimal("0.00")

    from app.services.exchange_service import get_rate_for_date

    for m in makbuzlar_in_period:
        if m.status in (Makbuz.STATUS_SENT, Makbuz.STATUS_PAID):
            makbuz_issued_try += m.grand_total
            
            m_work_orders = db.session.execute(
                db.select(WorkOrder)
                .where(
                    WorkOrder.party_id == m.party_id,
                    extract("year", WorkOrder.work_date) == m.year,
                    extract("month", WorkOrder.work_date) == m.month
                )
            ).scalars().all()
            
            m_subtotal_eur = Decimal("0.00")
            for wo in m_work_orders:
                rate = wo.exchange_rate_applied
                if not rate or rate <= 0:
                    rate_obj = get_rate_for_date(wo.work_date)
                    rate = rate_obj.eur_to_try if rate_obj else Decimal("1")
                if not rate or rate <= 0:
                    rate = Decimal("1")
                m_subtotal_eur += wo.total_price / rate
                
            if m.vat_applied:
                m_total_eur = m_subtotal_eur * (Decimal("1") + m.vat_rate / Decimal("100"))
            else:
                m_total_eur = m_subtotal_eur
            makbuz_issued_eur += m_total_eur

    issued_eur = legacy_issued_eur + makbuz_issued_eur
    issued_try = legacy_issued_try + makbuz_issued_try

    # 4. Calculate Collected (Payments)
    legacy_collected_eur = sum((p.amount_eur for p in payments), Decimal("0.00"))
    legacy_collected_try = sum((p.amount_try for p in payments), Decimal("0.00"))

    makbuz_collected_try = Decimal("0.00")
    makbuz_collected_eur = Decimal("0.00")
    makbuz_collections_in_period: list[tuple[date, Decimal]] = []

    for m in all_makbuzlar:
        if m.payment_entries:
            movements = [
                (entry.payment_date, entry.amount)
                for entry in m.payment_entries
                if start_date <= entry.payment_date <= end_date
            ]
        elif m.paid_at and m.paid_amount and start_date <= m.paid_at <= end_date:
            # Compatibility for databases not migrated yet and legacy test fixtures.
            movements = [(m.paid_at, m.paid_amount)]
        else:
            movements = []

        for payment_date, paid_try in movements:
            makbuz_collections_in_period.append((payment_date, paid_try))
            makbuz_collected_try += paid_try
            rate_obj = get_rate_for_date(payment_date)
            rate = rate_obj.eur_to_try if rate_obj else Decimal("1")
            if not rate or rate <= 0:
                rate = Decimal("1")
            makbuz_collected_eur += paid_try / rate

    collected_eur = legacy_collected_eur + makbuz_collected_eur
    collected_try = legacy_collected_try + makbuz_collected_try

    # 5. Calculate Outstanding & Overdue & Aging
    outstanding_eur = Decimal("0.00")
    outstanding_try = Decimal("0.00")
    overdue_eur = Decimal("0.00")
    
    aging = {
        "not_due": {"label": "Vadesi henüz gelmedi", "count": 0, "amount": Decimal("0.00")},
        "days_0_30": {"label": "1–30 gün gecikmiş", "count": 0, "amount": Decimal("0.00")},
        "days_31_60": {"label": "31–60 gün gecikmiş", "count": 0, "amount": Decimal("0.00")},
        "days_61_plus": {"label": "61+ gün gecikmiş", "count": 0, "amount": Decimal("0.00")},
    }
    receivable_count = 0

    # Legacy receivable invoices
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
        
        remaining_ratio = remaining_eur / invoice.total_eur if invoice.total_eur else Decimal("0")
        remaining_try = max(invoice.total_try * remaining_ratio, Decimal("0.00"))
        outstanding_eur += remaining_eur
        outstanding_try += remaining_try
        
        due_reference = invoice.due_date or invoice.invoice_date
        age_days = (end_date - due_reference).days
        if age_days <= 0:
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

    # New receivable makbuzlar
    for m in all_makbuzlar:
        m_date = date(m.year, m.month, 1)
        if m_date > end_date:
            continue
        if m.status not in (Makbuz.STATUS_SENT, Makbuz.STATUS_PAID):
            continue
            
        if m.payment_entries:
            collected_before_end = sum(
                (entry.amount for entry in m.payment_entries if entry.payment_date <= end_date),
                Decimal("0.00"),
            )
        elif m.paid_at and m.paid_at <= end_date:
            collected_before_end = m.paid_amount or Decimal("0.00")
        else:
            collected_before_end = Decimal("0.00")
        remaining_try = max(m.grand_total - collected_before_end, Decimal("0.00"))
        if remaining_try <= Decimal("0.01"):
            continue
        
        m_work_orders = db.session.execute(
            db.select(WorkOrder)
            .where(
                WorkOrder.party_id == m.party_id,
                extract("year", WorkOrder.work_date) == m.year,
                extract("month", WorkOrder.work_date) == m.month
            )
        ).scalars().all()
        
        m_subtotal_eur = Decimal("0.00")
        for wo in m_work_orders:
            rate = wo.exchange_rate_applied
            if not rate or rate <= 0:
                rate_obj = get_rate_for_date(wo.work_date)
                rate = rate_obj.eur_to_try if rate_obj else Decimal("1")
            if not rate or rate <= 0:
                rate = Decimal("1")
            m_subtotal_eur += wo.total_price / rate
            
        if m.vat_applied:
            full_total_eur = m_subtotal_eur * (Decimal("1") + m.vat_rate / Decimal("100"))
        else:
            full_total_eur = m_subtotal_eur
        remaining_ratio = remaining_try / m.grand_total if m.grand_total else Decimal("0")
        remaining_eur = full_total_eur * remaining_ratio
            
        if remaining_eur <= Decimal("0.01"):
            continue
            
        receivable_count += 1
        outstanding_eur += remaining_eur
        outstanding_try += remaining_try
        
        if m.month == 12:
            due_date = date(m.year + 1, 1, 15)
        else:
            due_date = date(m.year, m.month + 1, 15)
            
        age_days = (end_date - due_date).days
        if age_days <= 0:
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

    # 6. Treatment & Category Stats
    treatment_totals: dict[object, dict] = {}
    category_totals: dict[str, dict] = defaultdict(lambda: {"count": 0, "amount_eur": Decimal("0.00")})

    # Legacy Invoices
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

    # New WorkOrders
    import json
    def parse_wo_items(raw_str: str | None) -> list[dict]:
        if not raw_str:
            return []
        try:
            items = json.loads(raw_str)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        except (json.JSONDecodeError, TypeError):
            pass
        return [{"name": raw_str, "price": 0.0, "currency": "TL"}]

    for wo in work_orders_in_period:
        app_items = parse_wo_items(wo.apparatus_type)
        ext_items = parse_wo_items(wo.extra_addons)
        
        rate = wo.exchange_rate_applied or Decimal("1")
        if not rate or rate <= 0:
            rate_obj = get_rate_for_date(wo.work_date)
            rate = rate_obj.eur_to_try if rate_obj else Decimal("1")
        if not rate or rate <= 0:
            rate = Decimal("1")
            
        for item in app_items:
            price_try = Decimal(str(item.get("price") or 0))
            currency = item.get("currency", "TL")
            if price_try == 0:
                price_try = wo.apparatus_price
                currency = "TL"
            
            if currency == "EUR":
                item_eur = price_try
            elif currency == "USD":
                try_val = price_try * (wo.exchange_rate_applied or Decimal("1"))
                rate_obj = get_rate_for_date(wo.work_date)
                eur_rate = rate_obj.eur_to_try if rate_obj else Decimal("1")
                item_eur = try_val / (eur_rate or Decimal("1"))
            else:
                item_eur = price_try / rate
                
            category_key = "ana_islemler"
            category_totals[category_key]["count"] += 1
            category_totals[category_key]["amount_eur"] += item_eur
            
            name = item.get("name", "Bilinmeyen Aparey")
            row = treatment_totals.setdefault(name, {
                "name": name,
                "category": category_key,
                "count": 0,
                "amount_eur": Decimal("0.00"),
            })
            row["count"] += 1
            row["amount_eur"] += item_eur
            
        for item in ext_items:
            price_try = Decimal(str(item.get("price") or 0))
            currency = item.get("currency", "TL")
            if price_try == 0:
                price_try = wo.extra_price
                currency = "TL"
                
            if currency == "EUR":
                item_eur = price_try
            elif currency == "USD":
                try_val = price_try * (wo.exchange_rate_applied or Decimal("1"))
                rate_obj = get_rate_for_date(wo.work_date)
                eur_rate = rate_obj.eur_to_try if rate_obj else Decimal("1")
                item_eur = try_val / (eur_rate or Decimal("1"))
            else:
                item_eur = price_try / rate
                
            category_key = "ekstra_islemler"
            category_totals[category_key]["count"] += 1
            category_totals[category_key]["amount_eur"] += item_eur
            
            name = item.get("name", "Bilinmeyen Eklenti")
            row = treatment_totals.setdefault(name, {
                "name": name,
                "category": category_key,
                "count": 0,
                "amount_eur": Decimal("0.00"),
            })
            row["count"] += 1
            row["amount_eur"] += item_eur

    treatment_stats = sorted(
        treatment_totals.values(), key=lambda row: (row["count"], row["amount_eur"]), reverse=True
    )[:8]
    category_stats = [
        {"category": key, **value}
        for key, value in sorted(
            category_totals.items(), key=lambda pair: pair[1]["amount_eur"], reverse=True
        )
    ]

    # 7. Invoice & Makbuz Statuses
    status_counts = defaultdict(int)
    for invoice in invoices:
        status_counts[invoice.status] += 1
        
    for m in makbuzlar_in_period:
        if m.status == Makbuz.STATUS_PAID:
            status_counts[Invoice.STATUS_PAID] += 1
        elif m.status == Makbuz.STATUS_SENT:
            if m.month == 12:
                due_date = date(m.year + 1, 1, 15)
            else:
                due_date = date(m.year, m.month + 1, 15)
            if end_date > due_date:
                status_counts[Invoice.STATUS_OVERDUE] += 1
            else:
                status_counts[Invoice.STATUS_PENDING] += 1
        else:
            status_counts[Invoice.STATUS_PENDING] += 1

    invoice_statuses = [
        {"status": status, "label": STATUS_LABELS[status], "count": status_counts.get(status, 0)}
        for status in (Invoice.STATUS_PAID, Invoice.STATUS_PENDING, Invoice.STATUS_OVERDUE)
    ]

    current_rate = db.session.execute(
        db.select(ExchangeRate)
        .where(ExchangeRate.rate_date <= end_date)
        .order_by(ExchangeRate.rate_date.desc())
        .limit(1)
    ).scalar_one_or_none()

    trend_rows = _trend_rows(start_date, end_date, invoices, payments, work_orders_in_period, makbuz_collections_in_period)
    max_trend_value = max(
        (max(row["issued"], row["collected"]) for row in trend_rows), default=Decimal("1")
    ) or Decimal("1")
    max_category_amount = max((row["amount_eur"] for row in category_stats), default=Decimal("1")) or Decimal("1")
    max_aging_amount = max((row["amount"] for row in aging.values()), default=Decimal("1")) or Decimal("1")

    billed_count = len(invoices) + len([m for m in makbuzlar_in_period if m.status in (Makbuz.STATUS_SENT, Makbuz.STATUS_PAID)])
    total_payment_count = len(payments) + len(makbuz_collections_in_period)

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
        invoice_count=billed_count,
        payment_count=total_payment_count,
        treatment_stats=treatment_stats,
        category_stats=category_stats,
        category_labels=INVOICE_CATEGORY_LABELS,
        invoice_statuses=invoice_statuses,
        aging_rows=list(aging.values()),
        current_rate=current_rate,
        trend_rows=trend_rows,
        max_trend_value=max_trend_value,
        max_category_amount=max_category_amount,
        max_aging_amount=max_aging_amount,
    )
