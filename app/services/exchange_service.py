import requests
from datetime import date
from threading import Lock

from app.extensions import db
from app.models.models import ExchangeRate


_auto_check_lock = Lock()
_last_auto_check_date: date | None = None


def fetch_eur_try_rate() -> float:
    """Fetch current EUR/TRY rate from public providers with fallback."""
    providers = [
        "https://api.frankfurter.dev/v2/rate/EUR/TRY",
        "https://api.frankfurter.app/latest?from=EUR&to=TRY",
    ]

    last_error: Exception | None = None
    for url in providers:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if "rate" in data:
                return float(data["rate"])

            if "rates" in data and "TRY" in data["rates"]:
                return float(data["rates"]["TRY"])

            raise ValueError(f"Unexpected response schema from provider: {url}")
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"Failed to fetch EUR/TRY from providers: {last_error}")


def fetch_and_store_rate() -> float:
    """Fetch and store today's EUR/TRY rate."""
    rate_value = fetch_eur_try_rate()
    today = date.today()

    existing = db.session.execute(
        db.select(ExchangeRate).where(
            ExchangeRate.rate_date == today,
            ExchangeRate.source == "ecb",
        )
    ).scalar_one_or_none()

    if existing:
        existing.eur_to_try = rate_value
    else:
        db.session.add(ExchangeRate(
            rate_date=today,
            eur_to_try=rate_value,
            source="ecb",
        ))

    db.session.commit()
    return rate_value


def get_latest_rate() -> float | None:
    """Get the most recent EUR/TRY rate."""
    rate = db.session.execute(
        db.select(ExchangeRate)
        .order_by(ExchangeRate.rate_date.desc())
        .limit(1)
    ).scalar_one_or_none()
    return rate.eur_to_try if rate else None


def get_rate_health(max_age_days: int = 2) -> dict:
    """Return current rate health information for UI warnings."""
    latest = db.session.execute(
        db.select(ExchangeRate)
        .order_by(ExchangeRate.rate_date.desc())
        .limit(1)
    ).scalar_one_or_none()

    if latest is None:
        return {
            "exists": False,
            "is_stale": True,
            "age_days": None,
            "last_date": None,
            "last_rate": None,
        }

    age_days = (date.today() - latest.rate_date).days
    return {
        "exists": True,
        "is_stale": age_days > max_age_days,
        "age_days": age_days,
        "last_date": latest.rate_date,
        "last_rate": latest.eur_to_try,
    }


def ensure_daily_rate(max_age_days: int = 2) -> dict:
    """Fetch today's rate once per process day and return health snapshot."""
    global _last_auto_check_date

    today = date.today()
    if _last_auto_check_date == today:
        return get_rate_health(max_age_days=max_age_days)

    with _auto_check_lock:
        if _last_auto_check_date == today:
            return get_rate_health(max_age_days=max_age_days)

        _last_auto_check_date = today

        try:
            fetch_and_store_rate()
            status = get_rate_health(max_age_days=max_age_days)
            status["updated_today"] = True
            return status
        except Exception as exc:
            status = get_rate_health(max_age_days=max_age_days)
            status["updated_today"] = False
            status["error"] = str(exc)
            return status
