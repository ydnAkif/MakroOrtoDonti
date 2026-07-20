import logging
import os

from flask import Flask, g, request, url_for

from .config import Config, is_insecure_secret
from .extensions import db, login_manager, csrf, migrate
from . import user_loader  # noqa: F401 - registers user_loader


logger = logging.getLogger(__name__)


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    if not app.testing and not app.debug:
        invalid_keys = [
            key
            for key in ("SECRET_KEY", "ENCRYPTION_KEY")
            if is_insecure_secret(app.config.get(key))
        ]
        if invalid_keys:
            names = ", ".join(invalid_keys)
            raise RuntimeError(
                f"{names} eksik, kısa veya güvenli olmayan varsayılan değeri kullanıyor. "
                "Production başlamadan önce her anahtar için ayrı, kalıcı ve güçlü "
                "bir değer tanımlayın."
            )

    if app.config.get("TRUST_PROXY"):
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    os.makedirs(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"), exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    # Register transactional audit listeners before handling requests.
    from .services import audit_service  # noqa: F401
    from .services.observability import init_observability
    init_observability(app)

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
    from .routes.health import health_bp
    from .routes.privacy import privacy_bp

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
    app.register_blueprint(health_bp)
    app.register_blueprint(privacy_bp, url_prefix="/privacy")

    @app.context_processor
    def inject_globals():
        from .models.models import Settings
        from .services.exchange_service import get_rate_health

        clinic_name = "Makro Ortodonti"
        try:
            row = db.session.execute(
                db.select(Settings.value).where(Settings.key == "clinic_name")
            ).scalar_one_or_none()
            if row:
                clinic_name = row
        except Exception:
            logger.debug("clinic_name ayarı okunamadı", exc_info=True)

        try:
            rate_health = get_rate_health(max_age_days=2)
        except Exception:
            logger.debug("Kur sağlık bilgisi okunamadı", exc_info=True)
            rate_health = None
        auto_rate_error = None
        def page_url(page: int) -> str:
            args = request.args.to_dict(flat=True)
            args["page"] = page
            return url_for(request.endpoint, **(request.view_args or {}), **args)

        return {
            "clinic_name": clinic_name,
            "rate_health": rate_health,
            "auto_rate_error": auto_rate_error,
            "page_url": page_url,
            "party_type_labels": {
                "patient": "Hastalar",
                "dentist_customer": "Diş Hekimi Müşterileri",
                "company_customer": "Kurumsal Müşteriler",
                "": "Müşteriler",
            },
        }

    @app.cli.command("refresh-exchange-rate")
    def refresh_exchange_rate_command():
        """Scheduler-safe daily exchange-rate job."""
        from .services.exchange_service import fetch_and_store_rate
        rate = fetch_and_store_rate()
        print(f"EUR/TRY rate stored: {rate}")

    @app.cli.command("purge-expired-audit-logs")
    def purge_expired_audit_logs_command():
        """Delete audit rows older than the configured retention period."""
        from datetime import datetime, timedelta, timezone
        from .models.models import AuditLog
        days = int(app.config.get("AUDIT_RETENTION_DAYS", 3650))
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        result = db.session.execute(db.delete(AuditLog).where(AuditLog.occurred_at < cutoff))
        db.session.commit()
        print(f"Purged {result.rowcount or 0} audit rows older than {days} days")

    return app
