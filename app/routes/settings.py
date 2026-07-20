from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from datetime import date

from app.extensions import db
from app.models.models import Settings, ExchangeRate
from app.authz import permissions_required

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/")
@login_required
@permissions_required("settings.manage")
def index():
    settings = db.session.execute(db.select(Settings)).scalars().all()
    settings_dict = {s.key: s.value for s in settings}

    exchange_rates = db.session.execute(
        db.select(ExchangeRate).order_by(ExchangeRate.rate_date.desc()).limit(30)
    ).scalars().all()

    smtp_password_configured = bool(settings_dict.get("smtp_password"))

    return render_template(
        "settings/index.html",
        settings=settings_dict,
        smtp_password_configured=smtp_password_configured,
        exchange_rates=exchange_rates,
        today=date.today(),
    )


@settings_bp.route("/update", methods=["POST"])
@login_required
@permissions_required("settings.manage")
def update_settings():
    allowed_keys = {
        "clinic_name", "clinic_address", "clinic_phone", "clinic_email",
        "tax_id", "invoice_prefix", "invoice_footer_text",
        "smtp_server", "smtp_port", "smtp_username", "smtp_password",
    }

    submitted_keys = [key for key in request.form.keys() if key in allowed_keys]
    if not submitted_keys:
        flash("Güncellenecek ayar bulunamadı.", "warning")
        return redirect(url_for("settings.index"))

    for key in submitted_keys:
        value = request.form.get(key, "").strip()
        
        if key == "smtp_password":
            if not value:
                continue
            from app.services.security_service import encrypt_value
            value = encrypt_value(value)

        setting = db.session.execute(
            db.select(Settings).where(Settings.key == key)
        ).scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            db.session.add(Settings(key=key, value=value))

    db.session.commit()
    flash("Ayarlar güncellendi.", "success")
    return redirect(url_for("settings.index"))


@settings_bp.route("/exchange-rate/add", methods=["POST"])
@login_required
@permissions_required("settings.manage")
def add_exchange_rate():
    rate_date_str = request.form.get("rate_date", "")
    rate_value = request.form.get("eur_try_rate", "")

    if not rate_date_str or not rate_value:
        flash("Tarih ve kur değeri zorunludur.", "danger")
        return redirect(url_for("settings.index"))

    from app.services.validation_service import parse_date, parse_decimal
    rate_date = parse_date(rate_date_str)
    eur_try_rate = parse_decimal(rate_value, "0.0001")

    if not rate_date or eur_try_rate is None or eur_try_rate <= 0:
        flash("Geçersiz tarih veya kur değeri girildi.", "danger")
        return redirect(url_for("settings.index"))

    existing = db.session.execute(
        db.select(ExchangeRate).where(
            ExchangeRate.rate_date == rate_date,
            ExchangeRate.source == "ecb"
        )
    ).scalar_one_or_none()

    if existing:
        existing.eur_to_try = eur_try_rate
    else:
        db.session.add(ExchangeRate(
            rate_date=rate_date,
            eur_to_try=eur_try_rate,
            source="ecb",
        ))

    db.session.commit()
    flash(f"{rate_date} tarihli kur eklendi/güncellendi.", "success")
    return redirect(url_for("settings.index"))


@settings_bp.route("/exchange-rate/fetch", methods=["POST"])
@login_required
@permissions_required("settings.manage")
def fetch_exchange_rate():
    from app.services.exchange_service import fetch_and_store_rate
    try:
        rate = fetch_and_store_rate()
        flash(f"Güncel kur: 1 EUR = {rate:.4f} TRY", "success")
    except Exception as e:
        flash(f"Kur çekilirken hata oluştu: {str(e)}", "danger")
    return redirect(url_for("settings.index"))
