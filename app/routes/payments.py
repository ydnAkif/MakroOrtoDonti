from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models.models import Party, PartyType, Makbuz, money
from app.authz import permissions_required

payments_bp = Blueprint("payments", __name__)

METHOD_LABELS = {
    "cash": "Nakit",
    "card": "Kredi / Banka Kartı",
    "transfer": "Havale / EFT",
    "check": "Çek",
    "other": "Diğer",
}


@payments_bp.route("/")
@login_required
@permissions_required("billing.view")
def list_payments():
    search = request.args.get("search", "").strip()
    year = request.args.get("year", type=int)
    active_tab = request.args.get("tab", "pending")
    if active_tab not in {"pending", "paid", "summary"}:
        active_tab = "pending"

    doctors_query = db.select(Party).where(
        Party.party_type == PartyType.DENTIST, Party.is_active == True
    )
    if search:
        from app.services.search_service import tr_contains

        doctors_query = doctors_query.where(tr_contains(Party.name, search))
    from app.services.search_service import tr_order

    doctors = db.session.execute(doctors_query.order_by(tr_order(Party.name))).scalars().all()

    makbuz_query = db.select(Makbuz)
    if year:
        makbuz_query = makbuz_query.where(Makbuz.year == year)
    all_makbuzlar = db.session.execute(makbuz_query).scalars().all()

    by_party: dict[int, list[Makbuz]] = {}
    for m in all_makbuzlar:
        by_party.setdefault(m.party_id, []).append(m)

    rows = []
    for party in doctors:
        m_list = by_party.get(party.id, [])
        billed = money(sum(
            (m.grand_total for m in m_list if m.status in (Makbuz.STATUS_SENT, Makbuz.STATUS_PAID)),
            Decimal("0.00"),
        ))
        paid = money(sum(
            (m.paid_amount or Decimal("0.00") for m in m_list if m.status == Makbuz.STATUS_PAID),
            Decimal("0.00"),
        ))
        rows.append({
            "party": party,
            "billed": billed,
            "paid": paid,
            "outstanding": money(billed - paid),
            "makbuz_count": len(m_list),
        })

    rows.sort(key=lambda r: r["outstanding"], reverse=True)

    grand_billed = money(sum((r["billed"] for r in rows), Decimal("0.00")))
    grand_paid = money(sum((r["paid"] for r in rows), Decimal("0.00")))
    grand_outstanding = money(sum((r["outstanding"] for r in rows), Decimal("0.00")))

    visible_party_ids = {party.id for party in doctors}
    pending_makbuzlar = sorted(
        (
            m for m in all_makbuzlar
            if m.status == Makbuz.STATUS_SENT and m.party_id in visible_party_ids
        ),
        key=lambda m: (m.year, m.month),
        reverse=True,
    )
    paid_makbuzlar = sorted(
        (
            m for m in all_makbuzlar
            if m.status == Makbuz.STATUS_PAID and m.party_id in visible_party_ids
        ),
        key=lambda m: (m.paid_at or date.min, m.year, m.month),
        reverse=True,
    )

    years = sorted({m.year for m in db.session.execute(db.select(Makbuz)).scalars().all()} | {date.today().year}, reverse=True)

    return render_template(
        "payments/list.html",
        rows=rows,
        pending_makbuzlar=pending_makbuzlar,
        paid_makbuzlar=paid_makbuzlar,
        method_labels=METHOD_LABELS,
        grand_billed=grand_billed,
        grand_paid=grand_paid,
        grand_outstanding=grand_outstanding,
        search=search,
        year=year,
        years=years,
        active_tab=active_tab,
    )


@payments_bp.route("/<int:makbuz_id>/mark-paid", methods=["GET", "POST"])
@login_required
@permissions_required("billing.edit")
def mark_paid(makbuz_id):
    makbuz = db.get_or_404(Makbuz, makbuz_id)

    if request.method == "POST":
        from app.services.validation_service import parse_date, parse_decimal

        paid_date = parse_date(request.form.get("paid_at", "")) or date.today()
        paid_amount = parse_decimal(request.form.get("paid_amount", ""))
        method = request.form.get("payment_method", "cash")
        reference = request.form.get("payment_reference", "").strip() or None

        if paid_amount is None or paid_amount <= 0:
            flash("Geçerli bir ödeme tutarı girin.", "danger")
            return redirect(url_for("payments.mark_paid", makbuz_id=makbuz.id))

        makbuz.paid_at = paid_date
        makbuz.paid_amount = paid_amount
        makbuz.payment_method = method
        makbuz.payment_reference = reference
        makbuz.status = Makbuz.STATUS_PAID
        db.session.commit()
        flash(f"Ödeme kaydedildi: ₺{paid_amount:,.2f}", "success")
        return redirect(url_for("payments.list_payments", tab="paid"))

    return render_template(
        "payments/form.html",
        makbuz=makbuz,
        method_labels=METHOD_LABELS,
        today=date.today(),
    )


@payments_bp.route("/<int:makbuz_id>/unmark-paid", methods=["POST"])
@login_required
@permissions_required("billing.edit")
def unmark_paid(makbuz_id):
    makbuz = db.get_or_404(Makbuz, makbuz_id)
    makbuz.status = Makbuz.STATUS_SENT if makbuz.sent_at else Makbuz.STATUS_DRAFT
    makbuz.paid_at = None
    makbuz.paid_amount = None
    makbuz.payment_method = None
    makbuz.payment_reference = None
    db.session.commit()
    flash("Ödeme kaydı geri alındı.", "warning")
    return redirect(url_for("payments.list_payments"))
