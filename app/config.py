import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

_DEFAULT_DEV_KEY = "makro-orto-denti-dev-key-change-in-production"


class Config:
    _secret = os.environ.get("SECRET_KEY", "")
    _is_debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    _is_testing = (
        os.environ.get("TESTING", "false").lower() == "true"
        or os.environ.get("PYTEST_CURRENT_TEST") is not None
    )

    if not _secret or _secret == _DEFAULT_DEV_KEY:
        if not _is_debug and not _is_testing:
            # Production must have an explicit, strong SECRET_KEY.
            # Generating a random one-time key silently breaks sessions and
            # SMTP-password decryption on every restart.
            raise RuntimeError(
                "[FATAL] SECRET_KEY is missing or uses the insecure default value. "
                "Set a strong, stable SECRET_KEY in the environment or .env file "
                "before starting the application in production."
            )
        else:
            _secret = _DEFAULT_DEV_KEY

    SECRET_KEY = _secret

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///"
        + os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "makroortodonti.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

    # Session / cookie security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # SECURE flag is enabled only when not running locally in plain HTTP.
    # In production behind HTTPS this should be True; set via env var.
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
