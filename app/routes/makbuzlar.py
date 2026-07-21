from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, make_response
from flask_login import login_required
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.extensions import db
from app.models.models import WorkOrder, Party, Makbuz, money
from app.authz import permissions_required
from sqlalchemy import extract
from app.services.validation_service import parse_date

makbuzlar_bp = Blueprint("makbuzlar", __name__)

MONTHS = [
    (1, "Ocak"), (2, "Şubat"), (3, "Mart"), (4, "Nisan"),
    (5, "Mayıs"), (6, "Haziran"), (7, "Temmuz"), (8, "Ağustos"),
    (9, "Eylül"), (10, "Ekim"), (11, "Kasım"), (12, "Aralık"),
]

STATUS_LABELS = {
    Makbuz.STATUS_DRAFT: "Taslak",
    Makbuz.STATUS_SENT: "Tahsilat bekliyor",
    Makbuz.STATUS_PAID: "Ödendi",
}


def _work_orders_for_period(party_id: int, year: int, month: int) -> list[WorkOrder]:
    return db.session.execute(
        db.select(WorkOrder)
        .where(
            WorkOrder.party_id == party_id,
            extract("year", WorkOrder.work_date) == year,
            extract("month", WorkOrder.work_date) == month,
        )
        .order_by(WorkOrder.work_date.desc())
    ).scalars().all()


def _existing_makbuzlar(year: int, month: int) -> dict[int, Makbuz]:
    rows = db.session.execute(
        db.select(Makbuz).where(Makbuz.year == year, Makbuz.month == month)
    ).scalars().all()
    return {m.party_id: m for m in rows}


def _parse_vat_form(prefix: str = "") -> tuple[bool, Decimal]:
    vat_applied = request.form.get(f"{prefix}vat_applied") in ("on", "true", "1")
    try:
        vat_rate = Decimal(str(request.form.get(f"{prefix}vat_rate", "0") or "0").replace(",", "."))
    except InvalidOperation:
        vat_rate = Decimal("0")
    if vat_rate < 0:
        vat_rate = Decimal("0")
    return vat_applied, vat_rate


def _generate_makbuz(party_id: int, year: int, month: int, vat_applied: bool, vat_rate: Decimal) -> Makbuz:
    """Snapshot that period's work orders into a draft/updated Makbuz row."""
    existing = db.session.execute(
        db.select(Makbuz).where(
            Makbuz.party_id == party_id, Makbuz.year == year, Makbuz.month == month
        )
    ).scalar_one_or_none()

    if existing and existing.status != Makbuz.STATUS_DRAFT:
        raise ValueError("Gönderilmiş veya ödenmiş bir makbuz yeniden oluşturulamaz.")

    work_orders = _work_orders_for_period(party_id, year, month)
    subtotal = money(sum((wo.total_price for wo in work_orders), Decimal("0.00")))

    makbuz = existing or Makbuz(party_id=party_id, year=year, month=month)
    makbuz.work_order_count = len(work_orders)
    makbuz.subtotal = subtotal
    makbuz.vat_applied = vat_applied
    makbuz.vat_rate = vat_rate if vat_applied else Decimal("0.00")
    makbuz.status = Makbuz.STATUS_DRAFT
    makbuz.generated_at = datetime.now().astimezone()
    makbuz.recalculate_totals()

    if not existing:
        db.session.add(makbuz)
    db.session.flush()
    return makbuz


def _send_makbuz(makbuz: Makbuz) -> tuple[bool, str]:
    from app.services.makbuz_send_queue import send_makbuz_via_whatsapp

    return send_makbuz_via_whatsapp(makbuz.id)


@makbuzlar_bp.route("/")
@login_required
@permissions_required("billing.view")
def list_makbuzlar():
    year = request.args.get("year", date.today().year, type=int)
    month = request.args.get("month", date.today().month, type=int)

    work_orders = db.session.execute(
        db.select(WorkOrder)
        .join(Party, WorkOrder.party_id == Party.id)
        .where(
            extract("year", WorkOrder.work_date) == year,
            extract("month", WorkOrder.work_date) == month,
            Party.is_active == True,
        )
    ).scalars().all()

    makbuz_by_party = _existing_makbuzlar(year, month)

    doctor_data = {}
    for wo in work_orders:
        pid = wo.party_id
        if pid not in doctor_data:
            doctor_data[pid] = {
                "party": wo.party,
                "party_id": pid,
                "count": 0,
                "total_apparatus": Decimal("0.00"),
                "total_extra": Decimal("0.00"),
                "total_price": Decimal("0.00"),
                "makbuz": makbuz_by_party.get(pid),
            }
        d = doctor_data[pid]
        d["count"] += 1
        d["total_apparatus"] += wo.apparatus_price
        d["total_extra"] += wo.extra_price
        d["total_price"] += wo.total_price

    for pid, makbuz in makbuz_by_party.items():
        if pid not in doctor_data and makbuz.party and makbuz.party.is_active:
            doctor_data[pid] = {
                "party": makbuz.party,
                "party_id": pid,
                "count": makbuz.work_order_count or 0,
                "total_apparatus": Decimal("0.00"),
                "total_extra": Decimal("0.00"),
                "total_price": makbuz.subtotal or Decimal("0.00"),
                "makbuz": makbuz,
            }

    doctors = sorted(doctor_data.values(), key=lambda x: x["total_price"], reverse=True)

    grand_total_apparatus = sum(d["total_apparatus"] for d in doctors)
    grand_total_extra = sum(d["total_extra"] for d in doctors)
    grand_total_price = sum(
        (d["makbuz"].grand_total if d["makbuz"] else d["total_price"])
        for d in doctors
    )
    grand_total_count = sum(d["count"] for d in doctors)
    preparation_count = sum(
        1 for d in doctors
        if d["makbuz"] is None or d["makbuz"].status == Makbuz.STATUS_DRAFT
    )
    draft_count = sum(
        1 for d in doctors
        if d["makbuz"] and d["makbuz"].status == Makbuz.STATUS_DRAFT
    )
    awaiting_payment_count = sum(
        1 for d in doctors
        if d["makbuz"] and d["makbuz"].status == Makbuz.STATUS_SENT
    )

    return render_template(
        "makbuzlar/list.html",
        doctors=doctors,
        year=year,
        month=month,
        months=MONTHS,
        status_labels=STATUS_LABELS,
        preparation_count=preparation_count,
        draft_count=draft_count,
        awaiting_payment_count=awaiting_payment_count,
        sending=request.args.get("sending") == "1",
        grand_total_apparatus=grand_total_apparatus,
        grand_total_extra=grand_total_extra,
        grand_total_price=grand_total_price,
        grand_total_count=grand_total_count,
    )


@makbuzlar_bp.route("/<int:party_id>")
@login_required
@permissions_required("billing.view")
def detail_makbuz(party_id):
    party = db.get_or_404(Party, party_id)
    year = request.args.get("year", date.today().year, type=int)
    month = request.args.get("month", date.today().month, type=int)

    work_orders = _work_orders_for_period(party_id, year, month)

    total_apparatus = sum((wo.apparatus_price for wo in work_orders), Decimal("0.00"))
    total_extra = sum((wo.extra_price for wo in work_orders), Decimal("0.00"))
    total_price = sum((wo.total_price for wo in work_orders), Decimal("0.00"))

    makbuz = db.session.execute(
        db.select(Makbuz).where(
            Makbuz.party_id == party_id, Makbuz.year == year, Makbuz.month == month
        )
    ).scalar_one_or_none()

    return render_template(
        "makbuzlar/detail.html",
        party=party,
        work_orders=work_orders,
        year=year,
        month=month,
        months=MONTHS,
        status_labels=STATUS_LABELS,
        makbuz=makbuz,
        total_apparatus=total_apparatus,
        total_extra=total_extra,
        total_price=total_price,
    )


@makbuzlar_bp.route("/<int:party_id>/generate", methods=["POST"])
@login_required
@permissions_required("billing.edit")
def generate_makbuz(party_id):
    year = request.form.get("year", date.today().year, type=int)
    month = request.form.get("month", date.today().month, type=int)
    vat_applied, vat_rate = _parse_vat_form()

    try:
        makbuz = _generate_makbuz(party_id, year, month, vat_applied, vat_rate)
        db.session.commit()
        flash(f"Makbuz taslağı oluşturuldu: ₺{makbuz.grand_total:,.2f}", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")

    return redirect(url_for("makbuzlar.detail_makbuz", party_id=party_id, year=year, month=month))


@makbuzlar_bp.route("/<int:makbuz_id>/pdf")
@login_required
@permissions_required("billing.view")
def pdf_makbuz(makbuz_id):
    """Makbuz PDF'ini göndermeden önce tarayıcıda önizle veya indir."""
    from app.services.makbuz_pdf_service import generate_makbuz_pdf

    makbuz = db.get_or_404(Makbuz, makbuz_id)
    work_orders = _work_orders_for_period(makbuz.party_id, makbuz.year, makbuz.month)
    pdf_bytes = generate_makbuz_pdf(makbuz, work_orders)

    filename = f"makbuz_{makbuz.year}_{makbuz.month:02d}_{makbuz.party_id}.pdf"
    disposition = "attachment" if request.args.get("download") else "inline"
    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    return response


@makbuzlar_bp.route("/<int:makbuz_id>/send", methods=["POST"])
@login_required
@permissions_required("billing.edit")
def send_makbuz(makbuz_id):
    makbuz = db.get_or_404(Makbuz, makbuz_id)
    success, message = _send_makbuz(makbuz)
    flash(message, "success" if success else "danger")
    if request.form.get("return_to") == "list":
        return redirect(url_for(
            "makbuzlar.list_makbuzlar",
            year=makbuz.year,
            month=makbuz.month,
        ))
    return redirect(url_for("makbuzlar.detail_makbuz", party_id=makbuz.party_id, year=makbuz.year, month=makbuz.month))


@makbuzlar_bp.route("/bulk-send", methods=["POST"])
@login_required
@permissions_required("billing.edit")
def bulk_send_makbuzlar():
    """Send the selected doctors' ready drafts as one background batch."""
    from app.services.makbuz_send_queue import MakbuzSendQueue

    year = request.form.get("year", date.today().year, type=int)
    month = request.form.get("month", date.today().month, type=int)
    party_ids = request.form.getlist("party_ids", type=int)

    if not party_ids:
        flash("Gönderilecek doktor seçilmedi.", "danger")
        return redirect(url_for("makbuzlar.list_makbuzlar", year=year, month=month))

    makbuz_ids = db.session.execute(
        db.select(Makbuz.id).where(
            Makbuz.party_id.in_(party_ids),
            Makbuz.year == year,
            Makbuz.month == month,
            Makbuz.status == Makbuz.STATUS_DRAFT,
        )
    ).scalars().all()

    if not makbuz_ids:
        flash("Seçilen doktorlar için gönderilmeye hazır taslak yok.", "danger")
        return redirect(url_for("makbuzlar.list_makbuzlar", year=year, month=month))

    started, message = MakbuzSendQueue.start_batch(makbuz_ids)
    flash(message, "info" if started else "danger")
    return redirect(url_for(
        "makbuzlar.list_makbuzlar",
        year=year,
        month=month,
        sending=1 if started else None,
    ))


@makbuzlar_bp.route("/send-status")
@login_required
@permissions_required("billing.view")
def send_status():
    from app.services.makbuz_send_queue import MakbuzSendQueue

    return jsonify({"send_job": MakbuzSendQueue.current_job()})


@makbuzlar_bp.route("/bulk-generate", methods=["POST"])
@login_required
@permissions_required("billing.edit")
def bulk_generate_drafts():
    year = request.form.get("year", date.today().year, type=int)
    month = request.form.get("month", date.today().month, type=int)
    party_ids = request.form.getlist("party_ids", type=int)

    if not party_ids:
        flash("Taslak oluşturulacak doktor seçilmedi.", "danger")
        return redirect(url_for("makbuzlar.list_makbuzlar", year=year, month=month))

    generated, failed = 0, 0
    for pid in party_ids:
        vat_applied, vat_rate = _parse_vat_form(prefix=f"vat_{pid}_")
        try:
            _generate_makbuz(pid, year, month, vat_applied, vat_rate)
            db.session.commit()
            generated += 1
        except ValueError:
            db.session.rollback()
            failed += 1

    message = f"{generated} taslak makbuz oluşturuldu veya güncellendi."
    if failed:
        message += f" {failed} kilitli makbuz değiştirilemedi."
    flash(message, "success" if not failed else "warning")
    return redirect(url_for("makbuzlar.list_makbuzlar", year=year, month=month))


@makbuzlar_bp.route("/api/exchange-rate")
@login_required
@permissions_required("billing.edit")
def get_exchange_rate_for_date():
    """Return the EUR/TRY rate for the requested date."""
    target_date = parse_date(request.args.get("date", ""))
    if not target_date:
        return jsonify({"error": "Geçersiz tarih"}), 400

    from app.services.exchange_service import get_rate_for_date
    rate = get_rate_for_date(target_date)
    if not rate:
        return jsonify({"error": "Bu tarih için kur bulunamadı"}), 404

    return jsonify({
        "rate": float(rate.eur_to_try),
        "usd_rate": float(rate.usd_to_try) if rate.usd_to_try is not None else None,
        "rate_date": rate.rate_date.isoformat(),
        "display_date": rate.rate_date.strftime("%d.%m.%Y"),
        "source": rate.source,
    })
