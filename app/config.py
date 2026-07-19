import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Resolve SECRET_KEY: if missing or default, generate a secure random token in production
    _secret = os.environ.get("SECRET_KEY")
    _is_debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    _is_testing = os.environ.get("TESTING", "false").lower() == "true" or os.environ.get("PYTEST_CURRENT_TEST") is not None
    
    if not _secret or _secret == "makro-orto-denti-dev-key-change-in-production":
        if not _is_debug and not _is_testing:
            import secrets
            _secret = secrets.token_hex(32)
            print("\n[CRITICAL WARNING] Default or missing SECRET_KEY in production! Generating a random one-time key.\n")
        else:
            _secret = "makro-orto-denti-dev-key-change-in-production"
            
    SECRET_KEY = _secret
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "makroortodonti.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
    
    SESSION_TYPE = "filesystem"
