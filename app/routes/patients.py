from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from datetime import date

from app.extensions import db
from app.models.models import Patient, PatientTreatment, Treatment, Invoice, ExchangeRate, Party, PartyType
from app.authz import roles_required

patients_bp = Blueprint("patients", __name__)


@patients_bp.route("/")
@login_required
def list_patients():
    search = request.args.get("search", "").strip()
    query = db.select(Party).where(
        Party.party_type == PartyType.PATIENT,
        Party.is_active == True
    )

    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            db.or_(
                Party.first_name.ilike(search_pattern),
                Party.last_name.ilike(search_pattern),
                Party.name.ilike(search_pattern),
                Party.phone.ilike(search_pattern),
                Party.email.ilike(search_pattern),
            )
        )

    query = query.order_by(Party.last_name, Party.first_name, Party.name)
    parties = db.session.execute(query).scalars().all()

    return render_template(
        "patients/list.html",
        patients=parties,
        search=search,
    )


@patients_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_patient():
    if request.method == "POST":
        # Create Party first
        party = Party(
            party_type=PartyType.PATIENT,
            name=f"{request.form['first_name'].strip()} {request.form['last_name'].strip()}",
            first_name=request.form["first_name"].strip(),
            last_name=request.form["last_name"].strip(),
            phone=request.form.get("phone", "").strip() or None,
            email=request.form.get("email", "").strip() or None,
            address=request.form.get("address", "").strip() or None,
            notes=request.form.get("notes", "").strip() or None,
            treatment_status=request.form.get("treatment_status", "active"),
        )
        db.session.add(party)
        db.session.flush()
        
        # Create Patient linked to Party
        patient = Patient(
            first_name=request.form["first_name"].strip(),
            last_name=request.form["last_name"].strip(),
            phone=request.form.get("phone", "").strip() or None,
            email=request.form.get("email", "").strip() or None,
            address=request.form.get("address", "").strip() or None,
            notes=request.form.get("notes", "").strip() or None,
            treatment_status=request.form.get("treatment_status", "active"),
            party_id=party.id,
        )
        db.session.add(patient)
        db.session.commit()
        flash(f"{patient.full_name} başarıyla eklendi.", "success")
        return redirect(url_for("patients.detail_patient", patient_id=patient.id))

    return render_template("patients/form.html", patient=None)


@patients_bp.route("/<int:patient_id>")
@login_required
def detail_patient(patient_id):
    patient = db.get_or_404(Patient, patient_id)

    patient_treatments = db.session.execute(
        db.select(PatientTreatment)
        .where(PatientTreatment.patient_id == patient_id)
        .order_by(PatientTreatment.treatment_date.desc())
    ).scalars().all()

    # Use party_id for invoices if available, fallback to patient_id
    party_id = patient.party_id
    if party_id:
        patient_invoices = db.session.execute(
            db.select(Invoice)
            .where(Invoice.party_id == party_id, Invoice.is_deleted == False)
            .order_by(Invoice.invoice_date.desc())
        ).scalars().all()
    else:
        patient_invoices = db.session.execute(
            db.select(Invoice)
            .where(Invoice.patient_id == patient_id, Invoice.is_deleted == False)
            .order_by(Invoice.invoice_date.desc())
        ).scalars().all()

    total_owed_eur = sum(inv.total_eur for inv in patient_invoices if inv.status == Invoice.STATUS_PENDING)
    total_owed_try = sum(inv.total_try for inv in patient_invoices if inv.status == Invoice.STATUS_PENDING)

    current_rate = db.session.execute(
        db.select(ExchangeRate).order_by(ExchangeRate.rate_date.desc()).limit(1)
    ).scalar_one_or_none()

    all_treatments = db.session.execute(
        db.select(Treatment).where(Treatment.is_active == True).order_by(Treatment.name)
    ).scalars().all()

    from datetime import date as date_today
    today = date_today.today().isoformat()

    return render_template(
        "patients/detail.html",
        patient=patient,
        patient_treatments=patient_treatments,
        patient_invoices=patient_invoices,
        total_owed_eur=total_owed_eur,
        total_owed_try=total_owed_try,
        current_rate=current_rate,
        all_treatments=all_treatments,
        today=today,
    )


@patients_bp.route("/<int:patient_id>/edit", methods=["GET", "POST"])
@login_required
def edit_patient(patient_id):
    patient = db.get_or_404(Patient, patient_id)

    if request.method == "POST":
        patient.first_name = request.form["first_name"].strip()
        patient.last_name = request.form["last_name"].strip()
        patient.phone = request.form.get("phone", "").strip() or None
        patient.email = request.form.get("email", "").strip() or None
        patient.address = request.form.get("address", "").strip() or None
        patient.notes = request.form.get("notes", "").strip() or None
        patient.treatment_status = request.form.get("treatment_status", "active")
        
        # Update linked Party
        if patient.party:
            party = patient.party
            party.name = f"{patient.first_name} {patient.last_name}"
            party.first_name = patient.first_name
            party.last_name = patient.last_name
            party.phone = patient.phone
            party.email = patient.email
            party.address = patient.address
            party.notes = patient.notes
            party.treatment_status = patient.treatment_status
        
        db.session.commit()
        flash(f"{patient.full_name} güncellendi.", "success")
        return redirect(url_for("patients.detail_patient", patient_id=patient.id))

    return render_template("patients/form.html", patient=patient)


@patients_bp.route("/<int:patient_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete_patient(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    patient.is_active = False
    if patient.party:
        patient.party.is_active = False
    db.session.commit()
    flash(f"{patient.full_name} silindi.", "warning")
    return redirect(url_for("patients.list_patients"))


@patients_bp.route("/<int:patient_id>/add-treatment", methods=["POST"])
@login_required
def add_patient_treatment(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    treatment_id = request.form.get("treatment_id", type=int)
    treatment_date_str = request.form.get("treatment_date", "")
    notes = request.form.get("notes", "").strip()
    price_override = request.form.get("price_override", "").strip()

    if not treatment_id or not treatment_date_str:
        flash("Tedavi ve tarih seçimi zorunludur.", "danger")
        return redirect(url_for("patients.detail_patient", patient_id=patient_id))

    treatment_date = date.fromisoformat(treatment_date_str)

    pt = PatientTreatment(
        patient_id=patient_id,
        treatment_id=treatment_id,
        treatment_date=treatment_date,
        notes=notes or None,
        price_override_eur=float(price_override) if price_override else None,
    )
    db.session.add(pt)
    db.session.commit()
    flash("Tedavi eklendi.", "success")
    return redirect(url_for("patients.detail_patient", patient_id=patient_id))
