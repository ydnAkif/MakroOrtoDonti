import os
from flask import Flask, g, request
from .config import Config
from .extensions import db, login_manager, csrf
from . import user_loader  # noqa: F401 - registers user_loader


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"), exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from .routes.auth import auth_bp
    from .routes.dashboard import dashboard_bp
    from .routes.patients import patients_bp
    from .routes.parties import parties_bp
    from .routes.treatments import treatments_bp
    from .routes.invoices import invoices_bp
    from .routes.payments import payments_bp
    from .routes.settings import settings_bp
    from .routes.whatsapp import whatsapp_bp
    from .routes.reports import reports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(patients_bp, url_prefix="/patients")
    app.register_blueprint(parties_bp, url_prefix="/parties")
    app.register_blueprint(treatments_bp, url_prefix="/treatments")
    app.register_blueprint(invoices_bp, url_prefix="/invoices")
    app.register_blueprint(payments_bp, url_prefix="/payments")
    app.register_blueprint(settings_bp, url_prefix="/settings")
    app.register_blueprint(whatsapp_bp, url_prefix="/whatsapp")
    app.register_blueprint(reports_bp, url_prefix="/reports")

    @app.before_request
    def auto_refresh_exchange_rate():
        if request.endpoint and request.endpoint.startswith("static"):
            return

        from .services.exchange_service import ensure_daily_rate

        try:
            g.rate_auto_status = ensure_daily_rate(max_age_days=2)
        except Exception:
            g.rate_auto_status = None

    @app.context_processor
    def inject_globals():
        from .models.models import Settings
        from .services.exchange_service import get_rate_health

        clinic_name = "Makro Ortodonti"
        try:
            with db.session.begin():
                row = db.session.execute(
                    db.select(Settings.value).where(Settings.key == "clinic_name")
                ).scalar_one_or_none()
                if row == "Makro Orto Denti":
                    db.session.execute(
                        db.update(Settings)
                        .where(Settings.key == "clinic_name")
                        .values(value="Makro Ortodonti")
                    )
                    clinic_name = "Makro Ortodonti"
                elif row:
                    clinic_name = row
        except Exception:
            pass

        rate_health = get_rate_health(max_age_days=2)
        auto_rate_error = None
        status = getattr(g, "rate_auto_status", None)
        if status and status.get("error"):
            auto_rate_error = status["error"]

        return {
            "clinic_name": clinic_name,
            "rate_health": rate_health,
            "auto_rate_error": auto_rate_error,
        }

    # Database self-healing migration:
    # Ensure any invoice marked as 'paid' has a corresponding payment record.
    with app.app_context():
        try:
            from app.models.models import Invoice, Payment, PaymentMethod, ExchangeRate
            
            invoices = db.session.execute(
                db.select(Invoice).where(Invoice.status == Invoice.STATUS_PAID)
            ).scalars().all()
            
            updated = False
            for inv in invoices:
                total_paid = sum(p.amount_eur for p in inv.payments)
                diff = inv.total_eur - total_paid
                if diff > 0.01:
                    rate = db.session.execute(
                        db.select(ExchangeRate)
                        .where(ExchangeRate.rate_date <= inv.invoice_date)
                        .order_by(ExchangeRate.rate_date.desc())
                        .limit(1)
                    ).scalar_one_or_none()
                    eur_to_try = rate.eur_to_try if rate else inv.exchange_rate
                    
                    payment = Payment(
                        invoice_id=inv.id,
                        payment_date=inv.invoice_date,
                        amount_eur=diff,
                        amount_try=round(diff * eur_to_try, 2),
                        exchange_rate=eur_to_try,
                        method=PaymentMethod.CASH,
                        reference="Otomatik Geçmiş Tahsilat",
                        notes="Veritabanı denetiminde eksik olan tahsilat kaydı otomatik tamamlandı.",
                    )
                    db.session.add(payment)
                    updated = True
            if updated:
                db.session.commit()
        except Exception:
            pass

    return app
