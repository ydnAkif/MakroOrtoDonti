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

        clinic_name = "Makro Orto Denti"
        try:
            with db.session.begin():
                row = db.session.execute(
                    db.select(Settings.value).where(Settings.key == "clinic_name")
                ).scalar_one_or_none()
                if row:
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

    return app
