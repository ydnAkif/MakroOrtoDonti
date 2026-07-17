from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, jsonify
from flask_login import login_required
from datetime import date, datetime
import io
import json

from app.extensions import db
from app.models.models import Invoice, InvoiceItem, Party, PatientTreatment, Treatment, ExchangeRate, InvoiceItemType
from app.models.invoice_service import InvoiceService
from app.authz import roles_required

invoices_bp = Blueprint("invoices", __name__)


@invoices_bp.route("/")
@login_required
def list_invoices():
    status = request.args.get("status", "")
    search = request.args.get("search", "").strip()

    query = db.select(Invoice).where(Invoice.is_deleted == False)

    if status:
        query = query.where(Invoice.status == status)
    if search:
        query = query.join(Party).where(
            db.or_(
                Invoice.invoice_number.ilike(f"%{search}%"),
                Party.name.ilike(f"%{search}%"),
            )
        )

    query = query.order_by(Invoice.invoice_date.desc())
    invoices = db.session.execute(query).scalars().all()

    return render_template(
        "invoices/list.html",
        invoices=invoices,
        selected_status=status,
        search=search,
    )


@invoices_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_invoice():
    if request.method == "POST":
        # Support both new format (party_id + items_json) and legacy format (patient_id + treatment_ids)
        party_id = request.form.get("party_id", type=int)
        patient_id = request.form.get("patient_id", type=int)
        invoice_date_str = request.form.get("invoice_date", "")
        due_date_str = request.form.get("due_date", "")
        notes = request.form.get("notes", "").strip()
        
        # Get items from form - support both legacy treatment_ids and new items_json
        items_json = request.form.get("items_json", "")
        treatment_ids = request.form.getlist("treatment_ids", type=int)
        
        # Determine party_id from patient_id if needed (legacy support)
        if not party_id and patient_id:
            # Find the party linked to this patient
            from app.models.models import Patient
            patient = db.session.get(Patient, patient_id)
            if patient and patient.party_id:
                party_id = patient.party_id
            else:
                # Create a party for this patient if needed
                from app.models.models import Party, PartyType
                party = Party(
                    party_type=PartyType.PATIENT,
                    name=f"{patient.first_name} {patient.last_name}",
                    first_name=patient.first_name,
                    last_name=patient.last_name,
                    phone=patient.phone,
                    email=patient.email,
                    address=patient.address,
                    notes=patient.notes,
                    date_of_birth=patient.date_of_birth,
                    treatment_status=patient.treatment_status,
                    is_active=patient.is_active,
                )
                db.session.add(party)
                db.session.flush()
                patient.party_id = party.id
                party_id = party.id

        if not party_id:
            flash("Müşteri seçimi zorunludur.", "danger")
            return redirect(url_for("invoices.add_invoice"))

        invoice_date = date.fromisoformat(invoice_date_str) if invoice_date_str else date.today()
        due_date = date.fromisoformat(due_date_str) if due_date_str else None

        try:
            if items_json:
                # New flexible item format
                items = json.loads(items_json)
                invoice = InvoiceService.create_invoice(
                    session=db.session,
                    party_id=party_id,
                    items=items,
                    invoice_date=invoice_date,
                    due_date=due_date,
                    notes=notes or None,
                )
            elif treatment_ids:
                # Legacy format - treatment_ids from patient treatments
                invoice = InvoiceService.create_invoice_from_treatments(
                    session=db.session,
                    party_id=party_id,
                    treatment_ids=treatment_ids,
                    invoice_date=invoice_date,
                    due_date=due_date,
                    notes=notes or None,
                )
            else:
                flash("En az bir kalem seçimi zorunludur.", "danger")
                return redirect(url_for("invoices.add_invoice"))
            flash(f"Fatura {invoice.invoice_number} oluşturuldu.", "success")
            return redirect(url_for("invoices.detail_invoice", invoice_id=invoice.id))
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("invoices.add_invoice"))

    # Get active parties for dropdown
    parties = db.session.execute(
        db.select(Party).where(Party.is_active == True).order_by(Party.name)
    ).scalars().all()

    # Get active treatments for treatment modal
    treatments = db.session.execute(
        db.select(Treatment).where(Treatment.is_active == True).order_by(Treatment.name)
    ).scalars().all()

    # Get patient treatments for legacy format
    patient_treatments = db.session.execute(
        db.select(PatientTreatment)
        .join(Treatment)
        .where(Treatment.is_active == True)
        .order_by(PatientTreatment.treatment_date.desc())
    ).scalars().all()

    current_rate = db.session.execute(
        db.select(ExchangeRate).order_by(ExchangeRate.rate_date.desc()).limit(1)
    ).scalar_one_or_none()

    # Prepare treatments for JSON serialization
    treatments_json = [
        {"id": t.id, "name": t.name, "price_eur": t.price_eur}
        for t in treatments
    ]

    return render_template(
        "invoices/form.html",
        parties=parties,
        patient_treatments=patient_treatments,
        treatments=treatments_json,
        current_rate=current_rate,
        today=date.today(),
    )


@invoices_bp.route("/<int:invoice_id>")
@login_required
def detail_invoice(invoice_id):
    invoice = db.get_or_404(Invoice, invoice_id)
    return render_template("invoices/detail.html", invoice=invoice)


@invoices_bp.route("/<int:invoice_id>/pdf")
@login_required
def download_pdf(invoice_id):
    invoice = db.get_or_404(Invoice, invoice_id)

    from app.services.pdf_service import generate_invoice_pdf
    pdf_bytes = generate_invoice_pdf(invoice)

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        download_name=f"fatura_{invoice.invoice_number}.pdf",
        as_attachment=True,
    )


@invoices_bp.route("/<int:invoice_id>/status", methods=["POST"])
@login_required
def update_status(invoice_id):
    invoice = db.get_or_404(Invoice, invoice_id)
    new_status = request.form.get("status", "")
    if new_status in [Invoice.STATUS_PENDING, Invoice.STATUS_PAID, Invoice.STATUS_OVERDUE, Invoice.STATUS_CANCELLED]:
        invoice.status = new_status
        db.session.commit()
        flash(f"Fatura durumu güncellendi: {new_status}", "success")
    return redirect(url_for("invoices.detail_invoice", invoice_id=invoice.id))


@invoices_bp.route("/<int:invoice_id>/send-email", methods=["POST"])
@login_required
def send_email(invoice_id):
    invoice = db.get_or_404(Invoice, invoice_id)

    from app.services.email_service import send_invoice_email
    success, message = send_invoice_email(invoice)

    if success:
        flash("E-posta başarıyla gönderildi.", "success")
    else:
        flash(f"E-posta gönderilemedi: {message}", "danger")

    return redirect(url_for("invoices.detail_invoice", invoice_id=invoice.id))


@invoices_bp.route("/<int:invoice_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete_invoice(invoice_id):
    invoice = db.get_or_404(Invoice, invoice_id)
    invoice.is_deleted = True
    db.session.commit()
    flash(f"Fatura {invoice.invoice_number} silindi.", "warning")
    return redirect(url_for("invoices.list_invoices"))


@invoices_bp.route("/api/treatment-price/<int:treatment_id>")
@login_required
def get_treatment_price(treatment_id):
    pt = db.session.get(PatientTreatment, treatment_id)
    if pt:
        return jsonify({
            "price_eur": pt.effective_price_eur,
            "treatment_name": pt.treatment.name,
        })
    return jsonify({"error": "Not found"}), 404


@invoices_bp.route("/api/party/<int:party_id>")
@login_required
def get_party_info(party_id):
    """Get party info for invoice form."""
    party = db.session.get(Party, party_id)
    if party:
        return jsonify({
            "id": party.id,
            "name": party.display_name,
            "phone": party.phone,
            "email": party.email,
            "address": party.address,
            "tax_id": party.tax_id,
            "party_type": party.party_type.value,
        })
    return jsonify({"error": "Not found"}), 404
