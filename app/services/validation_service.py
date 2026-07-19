from datetime import date
from enum import Enum

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
        return float(val_str.strip().replace(",", "."))  # handle decimal commas too
    except (ValueError, TypeError):
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
