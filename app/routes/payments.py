from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from datetime import date

from app.extensions import db
from app.models.models import Payment, PaymentMethod, Invoice, ExchangeRate
from app.authz import roles_required

payments_bp = Blueprint("payments", __name__)


@payments_bp.route("/")
@login_required
def list_payments():
    search = request.args.get("search", "").strip()
    method = request.args.get("method", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    query = db.select(Payment).join(Invoice)

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

    query = query.order_by(Payment.payment_date.desc())
    payments = db.session.execute(query).scalars().all()

    # Pending/Unpaid invoices
    pending_invoices = db.session.execute(
        db.select(Invoice)
        .where(Invoice.status.in_([Invoice.STATUS_PENDING, Invoice.STATUS_OVERDUE]))
        .order_by(Invoice.invoice_date.desc())
    ).scalars().all()

    # Totals
    total_eur = sum(p.amount_eur for p in payments)
    total_try = sum(p.amount_try for p in payments)

    return render_template(
        "payments/list.html",
        payments=payments,
        pending_invoices=pending_invoices,
        total_eur=total_eur,
        total_try=total_try,
        selected_method=method,
        search=search,
        start_date=start_date,
        end_date=end_date,
    )


@payments_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_payment():
    if request.method == "POST":
        from app.services.validation_service import parse_date, parse_enum, parse_float
        invoice_id = request.form.get("invoice_id", type=int)
        payment_date_str = request.form.get("payment_date", "")
        amount_eur = parse_float(request.form.get("amount_eur", ""))
        
        parsed_method = parse_enum(PaymentMethod, request.form.get("method", "cash"))
        if not parsed_method:
            parsed_method = PaymentMethod.CASH
            
        reference = request.form.get("reference", "").strip() or None
        notes = request.form.get("notes", "").strip() or None

        if not invoice_id or amount_eur is None or amount_eur <= 0:
            flash("Fatura ve geçerli tutar seçimi zorunludur.", "danger")
            return redirect(url_for("payments.add_payment"))

        invoice = db.get_or_404(Invoice, invoice_id)
        
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
        
        amount_try = round(amount_eur * rate.eur_to_try, 2)

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
        total_paid_eur = sum(p.amount_eur for p in invoice.payments) + amount_eur
        if total_paid_eur >= invoice.total_eur - 0.01:  # Small tolerance
            invoice.status = Invoice.STATUS_PAID
        elif invoice.status == Invoice.STATUS_OVERDUE:
            invoice.status = Invoice.STATUS_PENDING
        
        db.session.commit()
        flash(f"Ödeme kaydedildi: €{amount_eur:,.2f} (₺{amount_try:,.2f})", "success")
        return redirect(url_for("payments.list_payments"))

    selected_invoice_id = request.args.get("invoice_id", type=int)

    # Get unpaid/partially paid invoices for dropdown
    invoices_query = db.select(Invoice).where(Invoice.status.in_([Invoice.STATUS_PENDING, Invoice.STATUS_OVERDUE]))
    if selected_invoice_id:
        invoices_query = invoices_query.or_(Invoice.id == selected_invoice_id)

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
    payment_eur = payment.amount_eur
    db.session.delete(payment)
    
    remaining_paid = sum(p.amount_eur for p in invoice.payments)
    if remaining_paid <= 0:
        invoice.status = Invoice.STATUS_PENDING
    elif remaining_paid >= invoice.total_eur - 0.01:
        invoice.status = Invoice.STATUS_PAID
    else:
        invoice.status = Invoice.STATUS_PENDING
    
    db.session.commit()
    flash("Ödeme silindi.", "warning")
    return redirect(url_for("payments.list_payments"))