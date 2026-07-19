from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models.models import Payment, PaymentMethod, Invoice, ExchangeRate
from app.authz import roles_required

payments_bp = Blueprint("payments", __name__)


def _payment_status(invoice: Invoice, total_paid_eur: Decimal, as_of: date) -> str:
    if total_paid_eur >= invoice.total_eur - Decimal("0.01"):
        return Invoice.STATUS_PAID
    if invoice.due_date and invoice.due_date < as_of:
        return Invoice.STATUS_OVERDUE
    return Invoice.STATUS_PENDING


@payments_bp.route("/")
@login_required
def list_payments():
    search = request.args.get("search", "").strip()
    method = request.args.get("method", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    query = db.select(Payment).join(Invoice).where(Invoice.is_deleted == False)

    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            db.or_(
                Invoice.invoice_number.ilike(search_pattern),
                Payment.reference.ilike(search_pattern),
            )
        )
    from app.services.validation_service import parse_date, parse_enum
    if method:
        parsed_method = parse_enum(PaymentMethod, method)
        if parsed_method:
            query = query.where(Payment.method == parsed_method)
    if start_date:
        parsed_start = parse_date(start_date)
        if parsed_start:
            query = query.where(Payment.payment_date >= parsed_start)
    if end_date:
        parsed_end = parse_date(end_date)
        if parsed_end:
            query = query.where(Payment.payment_date <= parsed_end)

    filtered_ids = query.with_only_columns(Payment.id).order_by(None).subquery()
    total_eur, total_try = db.session.execute(
        db.select(
            db.func.coalesce(db.func.sum(Payment.amount_eur), 0),
            db.func.coalesce(db.func.sum(Payment.amount_try), 0),
        ).where(Payment.id.in_(db.select(filtered_ids.c.id)))
    ).one()

    query = query.order_by(Payment.payment_date.desc())
    pagination = db.paginate(query, page=max(request.args.get("page", 1, type=int), 1), per_page=30, max_per_page=100, error_out=False)
    payments = pagination.items

    # Pending/Unpaid invoices
    pending_invoices = db.session.execute(
        db.select(Invoice)
        .where(
            Invoice.status.in_([Invoice.STATUS_PENDING, Invoice.STATUS_OVERDUE]),
            Invoice.is_deleted == False,
        )
        .order_by(Invoice.invoice_date.desc())
    ).scalars().all()

    method_labels = {
        "cash": "Nakit",
        "card": "Kredi / Banka Kartı",
        "transfer": "Havale / EFT",
        "check": "Çek",
        "other": "Diğer",
    }

    return render_template(
        "payments/list.html",
        payments=payments,
        pending_invoices=pending_invoices,
        total_eur=total_eur,
        total_try=total_try,
        selected_method=method,
        method_labels=method_labels,
        search=search,
        start_date=start_date,
        end_date=end_date,
        pagination=pagination,
    )


@payments_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_payment():
    if request.method == "POST":
        from app.services.validation_service import parse_date, parse_enum, parse_decimal
        invoice_id = request.form.get("invoice_id", type=int)
        payment_date_str = request.form.get("payment_date", "")
        amount_eur = parse_decimal(request.form.get("amount_eur", ""))
        
        parsed_method = parse_enum(PaymentMethod, request.form.get("method", "cash"))
        if not parsed_method:
            parsed_method = PaymentMethod.CASH
            
        reference = request.form.get("reference", "").strip() or None
        notes = request.form.get("notes", "").strip() or None

        if not invoice_id or amount_eur is None or amount_eur <= 0:
            flash("Fatura ve geçerli tutar seçimi zorunludur.", "danger")
            return redirect(url_for("payments.add_payment"))

        invoice = db.get_or_404(Invoice, invoice_id)
        if invoice.is_deleted or invoice.status == Invoice.STATUS_CANCELLED:
            flash("Silinmiş veya iptal edilmiş faturaya ödeme eklenemez.", "danger")
            return redirect(url_for("payments.add_payment"))
        
        payment_date = parse_date(payment_date_str) if payment_date_str else date.today()
        if not payment_date:
            flash("Geçersiz ödeme tarihi girildi.", "danger")
            return redirect(url_for("payments.add_payment"))
        
        # Get exchange rate for payment date
        rate = db.session.execute(
            db.select(ExchangeRate)
            .where(ExchangeRate.rate_date <= payment_date)
            .order_by(ExchangeRate.rate_date.desc())
            .limit(1)
        ).scalar_one_or_none()
        
        if not rate:
            flash("Ödeme tarihi için döviz kuru bulunamadı.", "danger")
            return redirect(url_for("payments.add_payment"))
        
        amount_try = (amount_eur * rate.eur_to_try).quantize(Decimal("0.01"))

        total_paid_before = sum(p.amount_eur for p in invoice.payments)
        remaining_eur = max(invoice.total_eur - total_paid_before, Decimal("0.00"))
        if amount_eur > remaining_eur + Decimal("0.01"):
            flash(
                f"Ödeme kalan €{remaining_eur:,.2f} bakiyeyi aşamaz.",
                "danger",
            )
            return redirect(url_for("payments.add_payment", invoice_id=invoice.id))

        payment = Payment(
            invoice_id=invoice_id,
            payment_date=payment_date,
            amount_eur=amount_eur,
            amount_try=amount_try,
            exchange_rate=rate.eur_to_try,
            method=parsed_method,
            reference=reference,
            notes=notes,
        )
        db.session.add(payment)
        
        # Check if invoice is fully paid
        total_paid_eur = total_paid_before + amount_eur
        invoice.status = _payment_status(invoice, total_paid_eur, payment_date)
        
        db.session.commit()
        flash(f"Ödeme kaydedildi: €{amount_eur:,.2f} (₺{amount_try:,.2f})", "success")
        return redirect(url_for("payments.list_payments"))

    selected_invoice_id = request.args.get("invoice_id", type=int)

    # Get unpaid/partially paid invoices for dropdown
    if selected_invoice_id:
        invoices_query = db.select(Invoice).where(
            db.or_(
                Invoice.status.in_([Invoice.STATUS_PENDING, Invoice.STATUS_OVERDUE]),
                Invoice.id == selected_invoice_id,
            ),
            Invoice.is_deleted == False,
        )
    else:
        invoices_query = db.select(Invoice).where(
            Invoice.status.in_([Invoice.STATUS_PENDING, Invoice.STATUS_OVERDUE]),
            Invoice.is_deleted == False,
        )

    invoices = db.session.execute(
        invoices_query.order_by(Invoice.invoice_date.desc())
    ).scalars().all()

    return render_template(
        "payments/form.html",
        invoices=invoices,
        selected_invoice_id=selected_invoice_id,
        today=date.today(),
        current_rate=db.session.execute(
            db.select(ExchangeRate).order_by(ExchangeRate.rate_date.desc()).limit(1)
        ).scalar_one_or_none(),
    )


@payments_bp.route("/<int:payment_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete_payment(payment_id):
    payment = db.get_or_404(Payment, payment_id)
    invoice = payment.invoice
    
    # Recalculate invoice status
    db.session.delete(payment)

    remaining_paid = sum(
        p.amount_eur for p in invoice.payments if p.id != payment.id
    )
    invoice.status = _payment_status(invoice, remaining_paid, date.today())
    
    db.session.commit()
    flash("Ödeme silindi.", "warning")
    return redirect(url_for("payments.list_payments"))
