#!/usr/bin/env python3
"""
Production entrypoint — starts Gunicorn with sensible defaults.

Usage:
    python run_production.py

Environment variables:
    SECRET_KEY           Strong session-signing key (required)
    ENCRYPTION_KEY       Separate key for encrypted settings (required)
    PORT                 TCP port to listen on (default: 8000)
    WORKERS              Gunicorn worker processes (default: 2*CPU+1)
    BIND                 Full bind address, overrides PORT (default: 0.0.0.0:<PORT>)
    LOG_LEVEL            Gunicorn log level (default: info)
    ACCESS_LOG           Path to access log file, "-" for stdout (default: -)
    ERROR_LOG            Path to error log file, "-" for stderr (default: -)
    TIMEOUT              Worker timeout in seconds (default: 60)
    KEEPALIVE            Keep-alive timeout in seconds (default: 5)

SECRET_KEY and ENCRYPTION_KEY MUST be separate strong, random values;
the application refuses to start without them (see app/config.py).
"""

import multiprocessing
import os
import sys


from app.config import is_insecure_secret


def main() -> None:
    invalid_keys = [
        key
        for key in ("SECRET_KEY", "ENCRYPTION_KEY")
        if is_insecure_secret(os.environ.get(key, ""))
    ]
    if invalid_keys:
        print(
            "ERROR: Production için ayrı, güçlü ve kalıcı anahtarlar gerekli: "
            + ", ".join(invalid_keys),
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        import gunicorn.app.wsgiapp  # noqa: F401
    except ImportError:
        print(
            "ERROR: gunicorn is not installed. "
            "Run `pip install gunicorn` and try again.",
            file=sys.stderr,
        )
        sys.exit(1)

    port = os.environ.get("PORT", "8000")
    bind = os.environ.get("BIND", f"0.0.0.0:{port}")
    default_workers = min(multiprocessing.cpu_count() * 2 + 1, 4)
    workers = os.environ.get("WORKERS", str(default_workers))
    log_level = os.environ.get("LOG_LEVEL", "info")
    access_log = os.environ.get("ACCESS_LOG", "-")
    error_log = os.environ.get("ERROR_LOG", "-")
    timeout = os.environ.get("TIMEOUT", "60")
    keepalive = os.environ.get("KEEPALIVE", "5")

    argv = [
        "gunicorn",
        "--bind", bind,
        "--workers", workers,
        "--worker-class", "sync",
        "--timeout", timeout,
        "--keep-alive", keepalive,
        "--log-level", log_level,
        "--access-logfile", access_log,
        "--error-logfile", error_log,
        "--forwarded-allow-ips", os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1"),
        "run:app",
    ]

    print(f"Starting Gunicorn: bind={bind} workers={workers}", flush=True)
    sys.argv = argv
    gunicorn.app.wsgiapp.run()


if __name__ == "__main__":
    main()
