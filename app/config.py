import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


DEFAULT_DEV_SECRET = "makro-orto-denti-dev-key-change-in-production"
PLACEHOLDER_SECRET = "replace-with-a-long-random-secret"


def is_insecure_secret(value: object) -> bool:
    """Return whether a secret is missing, known-placeholder, or too short."""
    return (
        not isinstance(value, str)
        or len(value) < 32
        or value == DEFAULT_DEV_SECRET
        or value.startswith("replace-with-")
    )


class Config:
    DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    TESTING = os.environ.get("TESTING", "false").lower() == "true"
    SECRET_KEY = os.environ.get("SECRET_KEY", DEFAULT_DEV_SECRET)
    ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", DEFAULT_DEV_SECRET)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///"
        + os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data",
            "makroortodonti.db",
        ),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = (
        os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
    )
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    # Only enable when the app is behind a trusted reverse proxy.
    TRUST_PROXY = os.environ.get("TRUST_PROXY", "false").lower() == "true"
