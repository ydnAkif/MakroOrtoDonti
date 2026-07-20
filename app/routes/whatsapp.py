from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
from app.authz import permissions_required

from app.extensions import db
from app.models.models import Party, PartyType, Invoice, WhatsAppSession

whatsapp_bp = Blueprint("whatsapp", __name__)


@whatsapp_bp.route("/")
@login_required
@permissions_required("messaging.use")
def index():
    from app.services.whatsapp_service import WhatsAppService
    status = WhatsAppService.get_status()

    parties_with_phone = db.session.execute(
        db.select(Party).where(
            Party.is_active == True,
            Party.phone.isnot(None),
            Party.phone != "",
        )
    ).scalars().all()

    return render_template(
        "whatsapp/index.html",
        status=status,
        patients=parties_with_phone,
    )


@whatsapp_bp.route("/connect", methods=["POST"])
@login_required
@permissions_required("messaging.use")
def connect():
    from app.services.whatsapp_service import WhatsAppService
    phone = request.form.get("phone_number", "").strip()
    result = WhatsAppService.connect(phone_number=phone if phone else None)
    flash(result["message"], "success" if result["success"] else "danger")
    return redirect(url_for("whatsapp.index"))


@whatsapp_bp.route("/disconnect", methods=["POST"])
@login_required
@permissions_required("messaging.use")
def disconnect():
    from app.services.whatsapp_service import WhatsAppService
    result = WhatsAppService.disconnect()
    flash(result["message"], "success" if result["success"] else "danger")
    return redirect(url_for("whatsapp.index"))


@whatsapp_bp.route("/send", methods=["POST"])
@login_required
@permissions_required("messaging.use")
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
@permissions_required("messaging.use")
def send_invoice(invoice_id):
    from app.services.whatsapp_service import WhatsAppService
    invoice = db.get_or_404(Invoice, invoice_id)
    result = WhatsAppService.send_invoice_message(invoice)
    flash(result["message"], "success" if result["success"] else "danger")
    return redirect(url_for("makbuzlar.list_makbuzlar"))


@whatsapp_bp.route("/send-bulk", methods=["POST"])
@login_required
@permissions_required("messaging.use")
def send_bulk():
    from app.services.whatsapp_service import WhatsAppService
    import time

    message_template = request.form.get("message", "").strip()
    party_ids = request.form.getlist("patient_ids", type=int)

    if not message_template or not party_ids:
        flash("Mesaj ve en az bir kişi seçimi zorunludur.", "danger")
        return redirect(url_for("whatsapp.index"))

    success_count = 0
    fail_count = 0

    for pid in party_ids:
        party = db.session.get(Party, pid)
        if party and party.phone:
            result = WhatsAppService.send_message(party.phone, message_template)
            if result["success"]:
                success_count += 1
            else:
                fail_count += 1
            time.sleep(3)

    flash(f"Toplu gönderim tamamlandı: {success_count} başarılı, {fail_count} başarısız.", "info")
    return redirect(url_for("whatsapp.index"))


@whatsapp_bp.route("/status")
@login_required
@permissions_required("messaging.use")
def status():
    from app.services.whatsapp_service import WhatsAppService
    status = WhatsAppService.get_status()
    return jsonify(status)
