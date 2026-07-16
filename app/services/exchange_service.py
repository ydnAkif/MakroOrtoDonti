import requests
from datetime import date

from app.extensions import db
from app.models.models import ExchangeRate


def fetch_eur_try_rate() -> float:
    """Fetch current EUR/TRY rate from Frankfurter API (ECB data)."""
    resp = requests.get(
        "https://api.frankfurter.dev/v2/rate/EUR/TRY",
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return float(data["rate"])


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
