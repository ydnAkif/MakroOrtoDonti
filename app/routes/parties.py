from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from datetime import date

from app.extensions import db
from app.models.models import Party, PartyType, WorkOrder, Treatment, TreatmentCategory, ExchangeRate
from app.authz import permissions_required

parties_bp = Blueprint("parties", __name__)


def _get_treatments_by_category(category):
    treatments = db.session.execute(
        db.select(Treatment)
        .where(Treatment.category == category, Treatment.is_active == True)
        .order_by(Treatment.name)
    ).scalars().all()
    return [{"id": t.id, "name": t.name, "price": float(t.price_eur), "currency": t.currency} for t in treatments]


def _get_current_rate():
    rate = db.session.execute(
        db.select(ExchangeRate).order_by(ExchangeRate.rate_date.desc()).limit(1)
    ).scalar_one_or_none()
    return float(rate.eur_to_try) if rate else 0


@parties_bp.route("/")
@login_required
@permissions_required("clinical.view")
def list_parties():
    search = request.args.get("search", "").strip()

    query = db.select(Party).where(
        Party.party_type == PartyType.DENTIST,
        Party.is_active == True,
    )

    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            db.or_(
                Party.name.ilike(search_pattern),
                Party.phone.ilike(search_pattern),
                Party.email.ilike(search_pattern),
            )
        )

    query = query.order_by(Party.name)
    pagination = db.paginate(query, page=max(request.args.get("page", 1, type=int), 1), per_page=25, max_per_page=100, error_out=False)
    parties = pagination.items

    return render_template(
        "parties/list.html",
        parties=parties,
        search=search,
        pagination=pagination,
    )


@parties_bp.route("/add", methods=["GET", "POST"])
@login_required
@permissions_required("clinical.edit")
def add_party():
    if request.method == "POST":
        party = Party(
            party_type=PartyType.DENTIST,
            name=request.form.get("name", "").strip(),
            phone=request.form.get("phone", "").strip() or None,
            email=request.form.get("email", "").strip() or None,
            address=request.form.get("address", "").strip() or None,
            tax_id=request.form.get("tax_id", "").strip() or None,
            notes=request.form.get("notes", "").strip() or None,
            is_active=request.form.get("is_active") == "on",
        )
        db.session.add(party)
        db.session.commit()
        flash(f"{party.display_name} başarıyla eklendi.", "success")
        return redirect(url_for("parties.detail_party", party_id=party.id))

    return render_template("parties/form.html", party=None)


@parties_bp.route("/import", methods=["GET", "POST"])
@login_required
@permissions_required("clinical.edit")
def import_parties():
    """Diş hekimlerini Excel dosyasından toplu içe aktar (A: Ad, B: Telefon, C: E-posta, D: Adres, E: Vergi/TC No, F: Not)."""
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            flash("Dosya seçilmedi.", "danger")
            return redirect(url_for("parties.import_parties"))

        filename = (file.filename or "").lower()
        if not (filename.endswith(".xlsx") or filename.endswith(".xls")):
            flash("Yalnızca .xlsx veya .xls dosyaları desteklenir.", "danger")
            return redirect(url_for("parties.import_parties"))

        try:
            import io
            from openpyxl import load_workbook

            wb = load_workbook(io.BytesIO(file.read()), read_only=True, data_only=True)
            ws = wb.active
            added, updated, skipped = 0, 0, 0

            def _text(value, limit):
                return str(value).strip()[:limit] if value is not None and str(value).strip() else None

            for row in ws.iter_rows(min_row=2, values_only=True):
                name = _text(row[0] if row else None, 200)
                if not name:
                    skipped += 1
                    continue
                phone = _text(row[1] if len(row) > 1 else None, 20)
                email = _text(row[2] if len(row) > 2 else None, 200)
                address = _text(row[3] if len(row) > 3 else None, 2000)
                tax_id = _text(row[4] if len(row) > 4 else None, 50)
                notes = _text(row[5] if len(row) > 5 else None, 2000)

                existing = db.session.execute(
                    db.select(Party).where(
                        Party.party_type == PartyType.DENTIST,
                        db.or_(
                            db.func.lower(Party.name) == name.lower(),
                            db.and_(Party.phone.isnot(None), Party.phone == phone) if phone else db.false(),
                        ),
                    )
                ).scalars().first()

                if existing:
                    existing.phone = phone or existing.phone
                    existing.email = email or existing.email
                    existing.address = address or existing.address
                    existing.tax_id = tax_id or existing.tax_id
                    existing.notes = notes or existing.notes
                    existing.is_active = True
                    updated += 1
                else:
                    db.session.add(Party(
                        party_type=PartyType.DENTIST, name=name, phone=phone,
                        email=email, address=address, tax_id=tax_id, notes=notes,
                        is_active=True,
                    ))
                    added += 1

            db.session.commit()
            wb.close()
            flash(f"İçe aktarma tamamlandı: {added} yeni, {updated} güncellendi, {skipped} atlandı.", "success")
            return redirect(url_for("parties.list_parties"))
        except Exception as e:
            db.session.rollback()
            flash(f"İçe aktarma hatası: {str(e)}", "danger")
            return redirect(url_for("parties.import_parties"))

    return render_template("parties/import.html")


@parties_bp.route("/<int:party_id>")
@login_required
@permissions_required("clinical.view")
def detail_party(party_id):
    party = db.get_or_404(Party, party_id)

    work_orders = db.session.execute(
        db.select(WorkOrder)
        .where(WorkOrder.party_id == party_id)
        .order_by(WorkOrder.work_date.desc())
    ).scalars().all()

    total_apparatus = sum(wo.apparatus_price for wo in work_orders)
    total_extra = sum(wo.extra_price for wo in work_orders)
    total_overall = sum(wo.total_price for wo in work_orders)

    return render_template(
        "parties/detail.html",
        party=party,
        work_orders=work_orders,
        total_apparatus=total_apparatus,
        total_extra=total_extra,
        total_overall=total_overall,
    )


@parties_bp.route("/<int:party_id>/edit", methods=["GET", "POST"])
@login_required
@permissions_required("clinical.edit")
def edit_party(party_id):
    party = db.get_or_404(Party, party_id)

    if request.method == "POST":
        party.name = request.form.get("name", "").strip()
        party.phone = request.form.get("phone", "").strip() or None
        party.email = request.form.get("email", "").strip() or None
        party.address = request.form.get("address", "").strip() or None
        party.tax_id = request.form.get("tax_id", "").strip() or None
        party.notes = request.form.get("notes", "").strip() or None
        party.is_active = request.form.get("is_active") == "on"

        db.session.commit()
        flash(f"{party.display_name} güncellendi.", "success")
        return redirect(url_for("parties.detail_party", party_id=party.id))

    return render_template("parties/form.html", party=party)


@parties_bp.route("/<int:party_id>/delete", methods=["POST"])
@login_required
@permissions_required("clinical.delete")
def delete_party(party_id):
    party = db.get_or_404(Party, party_id)
    party.is_active = False
    db.session.commit()
    flash(f"{party.display_name} silindi.", "warning")
    return redirect(url_for("parties.list_parties"))


@parties_bp.route("/<int:party_id>/work-orders/add", methods=["GET", "POST"])
@login_required
@permissions_required("clinical.edit")
def add_work_order(party_id):
    party = db.get_or_404(Party, party_id)

    if request.method == "POST":
        from app.services.validation_service import parse_date, parse_float

        work_date = parse_date(request.form.get("work_date", ""))
        if not work_date:
            flash("Geçersiz tarih.", "danger")
            return redirect(url_for("parties.add_work_order", party_id=party.id))

        apparatus_price = parse_float(request.form.get("apparatus_price", "0")) or 0
        extra_price = parse_float(request.form.get("extra_price", "0")) or 0
        exchange_rate_applied = parse_float(request.form.get("exchange_rate_applied", "")) or None

        wo = WorkOrder(
            party_id=party_id,
            work_date=work_date,
            apparatus_type=request.form.get("apparatus_type", "").strip(),
            extra_addons=request.form.get("extra_addons", "").strip() or None,
            patient_name=request.form.get("patient_name", "").strip(),
            apparatus_price=apparatus_price,
            extra_price=extra_price,
            total_price=apparatus_price + extra_price,
            exchange_rate_applied=exchange_rate_applied,
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(wo)
        db.session.commit()
        flash("İş emri başarıyla eklendi.", "success")
        return redirect(url_for("parties.detail_party", party_id=party.id))

    today = date.today().isoformat()
    from app.services.exchange_service import get_latest_rate, get_latest_usd_rate
    return render_template(
        "parties/work_order_form.html",
        party=party,
        work_order=None,
        today=today,
        ana_islemler_treatments=_get_treatments_by_category(TreatmentCategory.ANA_ISLEMLER),
        ekstra_islemler_treatments=_get_treatments_by_category(TreatmentCategory.EKSTRA_ISLEMLER),
        eur_to_try=_get_current_rate(),
        usd_to_try=get_latest_usd_rate() or 0,
    )


@parties_bp.route("/<int:party_id>/work-orders/<int:wo_id>/edit", methods=["GET", "POST"])
@login_required
@permissions_required("clinical.edit")
def edit_work_order(party_id, wo_id):
    party = db.get_or_404(Party, party_id)
    wo = db.get_or_404(WorkOrder, wo_id)

    if request.method == "POST":
        from app.services.validation_service import parse_date, parse_float

        work_date = parse_date(request.form.get("work_date", ""))
        if not work_date:
            flash("Geçersiz tarih.", "danger")
            return redirect(url_for("parties.edit_work_order", party_id=party.id, wo_id=wo.id))

        apparatus_price = parse_float(request.form.get("apparatus_price", "0")) or 0
        extra_price = parse_float(request.form.get("extra_price", "0")) or 0
        exchange_rate_applied = parse_float(request.form.get("exchange_rate_applied", "")) or None

        wo.work_date = work_date
        wo.apparatus_type = request.form.get("apparatus_type", "").strip()
        wo.extra_addons = request.form.get("extra_addons", "").strip() or None
        wo.patient_name = request.form.get("patient_name", "").strip()
        wo.apparatus_price = apparatus_price
        wo.extra_price = extra_price
        wo.total_price = apparatus_price + extra_price
        wo.exchange_rate_applied = exchange_rate_applied
        wo.notes = request.form.get("notes", "").strip() or None

        db.session.commit()
        flash("İş emri güncellendi.", "success")
        return redirect(url_for("parties.detail_party", party_id=party.id))

    from app.services.exchange_service import get_latest_rate, get_latest_usd_rate
    return render_template(
        "parties/work_order_form.html",
        party=party,
        work_order=wo,
        today=wo.work_date.isoformat(),
        ana_islemler_treatments=_get_treatments_by_category(TreatmentCategory.ANA_ISLEMLER),
        ekstra_islemler_treatments=_get_treatments_by_category(TreatmentCategory.EKSTRA_ISLEMLER),
        eur_to_try=_get_current_rate(),
        usd_to_try=get_latest_usd_rate() or 0,
    )


@parties_bp.route("/<int:party_id>/work-orders/<int:wo_id>/delete", methods=["POST"])
@login_required
@permissions_required("clinical.delete")
def delete_work_order(party_id, wo_id):
    wo = db.get_or_404(WorkOrder, wo_id)
    db.session.delete(wo)
    db.session.commit()
    flash("İş emri silindi.", "warning")
    return redirect(url_for("parties.detail_party", party_id=party_id))
