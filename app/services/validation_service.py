from datetime import date
from enum import Enum
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from app.models.models import TreatmentCategory


TREATMENT_CATEGORY_ALIASES = {
    "ana_islemler": "ana_islemler", "ana işlemler": "ana_islemler",
    "ana islemler": "ana_islemler", "ana": "ana_islemler",
    "ekstra_islemler": "ekstra_islemler", "ekstra işlemler": "ekstra_islemler",
    "ekstra islemler": "ekstra_islemler", "ekstra": "ekstra_islemler",
}

VALID_CURRENCIES = ("TL", "EUR", "USD")


def normalize_treatment_fields(name, description, category, price_eur, currency=None):
    """Validate treatment input identically for forms, JSON and spreadsheets."""
    clean_name = str(name or "").strip()
    clean_description = str(description or "").strip() or None
    raw_category = str(category or "other").strip().lower()
    clean_category = TREATMENT_CATEGORY_ALIASES.get(raw_category)

    if not clean_name or len(clean_name) > 200:
        raise ValueError("İşlem adı 1–200 karakter olmalıdır.")
    if clean_description and len(clean_description) > 2000:
        raise ValueError("İşlem açıklaması 2000 karakteri aşamaz.")
    if clean_category not in TreatmentCategory.ALL:
        raise ValueError("Geçersiz işlem kategorisi.")

    price = parse_decimal(price_eur)
    if price is None:
        raise ValueError("Geçersiz işlem fiyatı; sayısal olmalıdır.")
    if price < 0:
        raise ValueError("İşlem fiyatı negatif olamaz.")

    clean_currency = str(currency or "TL").strip().upper()
    if clean_currency not in VALID_CURRENCIES:
        clean_currency = "TL"

    return clean_name, clean_description, clean_category, price, clean_currency

def parse_date(date_str: str) -> date | None:
    """Safely parse an ISO date string, returning None if malformed or empty."""
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str.strip())
    except ValueError:
        return None

def parse_float(val_str: str) -> float | None:
    """Safely parse a string value to float, returning None if malformed or empty."""
    if not val_str:
        return None
    try:
        return float(str(val_str).strip().replace(",", "."))
    except (ValueError, TypeError):
        return None

def parse_decimal(val_str: str, scale: str = "0.01") -> Decimal | None:
    """Parse user-entered decimal values without binary floating-point conversion."""
    if not val_str:
        return None
    try:
        value = Decimal(str(val_str).strip().replace(",", "."))
        if not value.is_finite():
            return None
        return value.quantize(Decimal(scale), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return None

def parse_int(val_str: str) -> int | None:
    """Safely parse a string value to integer, returning None if malformed or empty."""
    if not val_str:
        return None
    try:
        return int(val_str.strip())
    except (ValueError, TypeError):
        return None

def parse_enum(enum_class: type[Enum], val: str) -> Enum | None:
    """Safely parse a string value to an enum member, returning None if malformed or empty."""
    if not val:
        return None
    try:
        # Support either string value or name matching
        val_clean = val.strip()
        try:
            return enum_class(val_clean)
        except ValueError:
            return enum_class[val_clean]
    except (ValueError, KeyError, TypeError):
        return None
