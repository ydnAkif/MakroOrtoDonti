import os
from flask import Flask
from .config import Config
from .extensions import db, login_manager
from . import user_loader  # noqa: F401 - registers user_loader


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"), exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from .routes.auth import auth_bp
    from .routes.dashboard import dashboard_bp
    from .routes.patients import patients_bp
    from .routes.treatments import treatments_bp
    from .routes.invoices import invoices_bp
    from .routes.settings import settings_bp
    from .routes.whatsapp import whatsapp_bp
    from .routes.reports import reports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(patients_bp, url_prefix="/patients")
    app.register_blueprint(treatments_bp, url_prefix="/treatments")
    app.register_blueprint(invoices_bp, url_prefix="/invoices")
    app.register_blueprint(settings_bp, url_prefix="/settings")
    app.register_blueprint(whatsapp_bp, url_prefix="/whatsapp")
    app.register_blueprint(reports_bp, url_prefix="/reports")

    @app.context_processor
    def inject_globals():
        from .models.models import Settings
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
        return {"clinic_name": clinic_name}

    return app
