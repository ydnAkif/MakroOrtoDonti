from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from datetime import date

from app.extensions import db
from app.models.models import Party, PartyType, Treatment, Invoice, PatientTreatment, ExchangeRate
from app.authz import roles_required

parties_bp = Blueprint("parties", __name__)


@parties_bp.route("/")
@login_required
def list_parties():
    search = request.args.get("search", "").strip()
    party_type = request.args.get("type", "")

    query = db.select(Party).where(Party.is_active == True)

    if party_type:
        query = query.where(Party.party_type == PartyType(party_type))
    
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            db.or_(
                Party.name.ilike(search_pattern),
                Party.first_name.ilike(search_pattern),
                Party.last_name.ilike(search_pattern),
                Party.phone.ilike(search_pattern),
                Party.email.ilike(search_pattern),
                Party.tax_id.ilike(search_pattern),
            )
        )

    query = query.order_by(Party.name)
    parties = db.session.execute(query).scalars().all()

    type_labels = {
        "patient": "Hasta",
        "dentist_customer": "Diş Hekimi Müşterisi",
        "company_customer": "Kurumsal Müşteri",
    }

    return render_template(
        "parties/list.html",
        parties=parties,
        search=search,
        selected_type=party_type,
        type_labels=type_labels,
    )


@parties_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_party():
    if request.method == "POST":
        party = Party(
            party_type=PartyType(request.form["party_type"]),
            name=request.form.get("name", "").strip() or f"{request.form['first_name']} {request.form['last_name']}",
            first_name=request.form.get("first_name", "").strip() or None,
            last_name=request.form.get("last_name", "").strip() or None,
            date_of_birth=date.fromisoformat(request.form["date_of_birth"]) if request.form.get("date_of_birth") else None,
            phone=request.form.get("phone", "").strip() or None,
            email=request.form.get("email", "").strip() or None,
            address=request.form.get("address", "").strip() or None,
            tax_id=request.form.get("tax_id", "").strip() or None,
            notes=request.form.get("notes", "").strip() or None,
            treatment_status=request.form.get("treatment_status", "active"),
            contact_person=request.form.get("contact_person", "").strip() or None,
            contact_phone=request.form.get("contact_phone", "").strip() or None,
            is_active=request.form.get("is_active") == "on",
        )
        party.referred_by_id = request.form.get("referred_by_id", type=int)
        db.session.add(party)
        db.session.commit()
        flash(f"{party.display_name} başarıyla eklendi.", "success")
        return redirect(url_for("parties.detail_party", party_id=party.id))

    dentists = db.session.execute(
        db.select(Party).where(Party.party_type == PartyType.DENTIST_CUSTOMER, Party.is_active == True).order_by(Party.name)
    ).scalars().all()
    return render_template("parties/form.html", party=None, dentists=dentists)


@parties_bp.route("/<int:party_id>")
@login_required
def detail_party(party_id):
    party = db.get_or_404(Party, party_id)

    invoices = db.session.execute(
        db.select(Invoice)
        .where(Invoice.party_id == party_id, Invoice.is_deleted == False)
        .order_by(Invoice.invoice_date.desc())
    ).scalars().all()

    total_owed_eur = sum(inv.total_eur for inv in invoices if inv.status == Invoice.STATUS_PENDING)
    total_owed_try = sum(inv.total_try for inv in invoices if inv.status == Invoice.STATUS_PENDING)

    current_rate = db.session.execute(
        db.select(ExchangeRate).order_by(ExchangeRate.rate_date.desc()).limit(1)
    ).scalar_one_or_none()

    return render_template(
        "parties/detail.html",
        party=party,
        invoices=invoices,
        total_owed_eur=total_owed_eur,
        total_owed_try=total_owed_try,
        current_rate=current_rate,
    )


@parties_bp.route("/<int:party_id>/edit", methods=["GET", "POST"])
@login_required
def edit_party(party_id):
    party = db.get_or_404(Party, party_id)

    if request.method == "POST":
        party.party_type = PartyType(request.form["party_type"])
        party.name = request.form.get("name", "").strip() or (f"{request.form['first_name']} {request.form['last_name']}" if request.form.get("first_name") else request.form.get("company_name", ""))
        party.first_name = request.form.get("first_name", "").strip() or None
        party.last_name = request.form.get("last_name", "").strip() or None
        party.date_of_birth = date.fromisoformat(request.form["date_of_birth"]) if request.form.get("date_of_birth") else None
        party.phone = request.form.get("phone", "").strip() or None
        party.email = request.form.get("email", "").strip() or None
        party.address = request.form.get("address", "").strip() or None
        party.tax_id = request.form.get("tax_id", "").strip() or None
        party.notes = request.form.get("notes", "").strip() or None
        party.treatment_status = request.form.get("treatment_status", "active")
        party.contact_person = request.form.get("contact_person", "").strip() or None
        party.contact_phone = request.form.get("contact_phone", "").strip() or None
        party.is_active = request.form.get("is_active") == "on"
        party.referred_by_id = request.form.get("referred_by_id", type=int)
        
        db.session.commit()
        flash(f"{party.display_name} güncellendi.", "success")
        return redirect(url_for("parties.detail_party", party_id=party.id))

    dentists = db.session.execute(
        db.select(Party).where(Party.party_type == PartyType.DENTIST_CUSTOMER, Party.is_active == True).order_by(Party.name)
    ).scalars().all()
    return render_template("parties/form.html", party=party, dentists=dentists)


@parties_bp.route("/<int:party_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete_party(party_id):
    party = db.get_or_404(Party, party_id)
    party.is_active = False
    db.session.commit()
    flash(f"{party.display_name} silindi.", "warning")
    return redirect(url_for("parties.list_parties"))