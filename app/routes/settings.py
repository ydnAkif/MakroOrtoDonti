from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from datetime import date

from app.extensions import db
from app.models.models import Settings, ExchangeRate

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/")
@login_required
def index():
    settings = db.session.execute(db.select(Settings)).scalars().all()
    settings_dict = {s.key: s.value for s in settings}

    exchange_rates = db.session.execute(
        db.select(ExchangeRate).order_by(ExchangeRate.rate_date.desc()).limit(30)
    ).scalars().all()

    return render_template(
        "settings/index.html",
        settings=settings_dict,
        exchange_rates=exchange_rates,
    )


@settings_bp.route("/update", methods=["POST"])
@login_required
def update_settings():
    for key in [
        "clinic_name", "clinic_address", "clinic_phone", "clinic_email",
        "tax_id", "invoice_prefix", "invoice_footer_text",
        "smtp_server", "smtp_port", "smtp_username", "smtp_password",
    ]:
        value = request.form.get(key, "").strip()
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
def add_exchange_rate():
    rate_date_str = request.form.get("rate_date", "")
    rate_value = request.form.get("eur_try_rate", "")

    if not rate_date_str or not rate_value:
        flash("Tarih ve kur değeri zorunludur.", "danger")
        return redirect(url_for("settings.index"))

    rate_date = date.fromisoformat(rate_date_str)
    eur_try_rate = float(rate_value)

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
def fetch_exchange_rate():
    from app.services.exchange_service import fetch_and_store_rate
    try:
        rate = fetch_and_store_rate()
        flash(f"Güncel kur: 1 EUR = {rate:.4f} TRY", "success")
    except Exception as e:
        flash(f"Kur çekilirken hata oluştu: {str(e)}", "danger")
    return redirect(url_for("settings.index"))
