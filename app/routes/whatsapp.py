from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required

from app.extensions import db
from app.models.models import Patient, Invoice, WhatsAppSession

whatsapp_bp = Blueprint("whatsapp", __name__)


@whatsapp_bp.route("/")
@login_required
def index():
    from app.services.whatsapp_service import WhatsAppService
    status = WhatsAppService.get_status()

    patients_with_phone = db.session.execute(
        db.select(Patient).where(
            Patient.is_active == True,
            Patient.phone.isnot(None),
            Patient.phone != "",
        )
    ).scalars().all()

    return render_template(
        "whatsapp/index.html",
        status=status,
        patients=patients_with_phone,
    )


@whatsapp_bp.route("/connect", methods=["POST"])
@login_required
def connect():
    from app.services.whatsapp_service import WhatsAppService
    phone = request.form.get("phone_number", "").strip()
    result = WhatsAppService.connect(phone_number=phone if phone else None)
    flash(result["message"], "success" if result["success"] else "danger")
    return redirect(url_for("whatsapp.index"))


@whatsapp_bp.route("/disconnect", methods=["POST"])
@login_required
def disconnect():
    from app.services.whatsapp_service import WhatsAppService
    result = WhatsAppService.disconnect()
    flash(result["message"], "success" if result["success"] else "danger")
    return redirect(url_for("whatsapp.index"))


@whatsapp_bp.route("/send", methods=["POST"])
@login_required
def send_message():
    from app.services.whatsapp_service import WhatsAppService
    phone = request.form.get("phone_number", "").strip()
    message = request.form.get("message", "").strip()

    if not phone or not message:
        flash("Telefon numarası ve mesaj zorunludur.", "danger")
        return redirect(url_for("whatsapp.index"))

    result = WhatsAppService.send_message(phone, message)
    flash(result["message"], "success" if result["success"] else "danger")
    return redirect(url_for("whatsapp.index"))


@whatsapp_bp.route("/send-invoice/<int:invoice_id>", methods=["POST"])
@login_required
def send_invoice(invoice_id):
    from app.services.whatsapp_service import WhatsAppService
    invoice = db.get_or_404(Invoice, invoice_id)
    result = WhatsAppService.send_invoice_message(invoice)
    flash(result["message"], "success" if result["success"] else "danger")
    return redirect(url_for("invoices.detail_invoice", invoice_id=invoice.id))


@whatsapp_bp.route("/send-bulk", methods=["POST"])
@login_required
def send_bulk():
    from app.services.whatsapp_service import WhatsAppService
    import time

    message_template = request.form.get("message", "").strip()
    patient_ids = request.form.getlist("patient_ids", type=int)

    if not message_template or not patient_ids:
        flash("Mesaj ve en az bir hasta seçimi zorunludur.", "danger")
        return redirect(url_for("whatsapp.index"))

    success_count = 0
    fail_count = 0

    for pid in patient_ids:
        patient = db.session.get(Patient, pid)
        if patient and patient.phone:
            result = WhatsAppService.send_message(patient.phone, message_template)
            if result["success"]:
                success_count += 1
            else:
                fail_count += 1
            time.sleep(3)  # Delay between messages

    flash(f"Toplu gönderim tamamlandı: {success_count} başarılı, {fail_count} başarısız.", "info")
    return redirect(url_for("whatsapp.index"))


@whatsapp_bp.route("/status")
@login_required
def status():
    from app.services.whatsapp_service import WhatsAppService
    status = WhatsAppService.get_status()
    return jsonify(status)
