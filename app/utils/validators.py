import re

from app.config import settings


def clean_phone(raw_phone: str) -> str:
    """Normalize a raw phone string to E.164 format, or return empty string if unrecognized."""
    if not raw_phone:
        return ""

    # Keep only digits and leading plus
    digits = re.sub(r"[^\d+]", "", raw_phone)

    # Already in correct international format
    if digits.startswith("+"):
        return digits

    # Normalize Ukrainian numbers (missing plus or leading zero)
    if digits.startswith("380") and len(digits) == 12:
        return f"+{digits}"
    if digits.startswith("0") and len(digits) == 10:
        return f"+38{digits}"

    # Normalize US numbers (missing plus)
    if digits.startswith("1") and len(digits) == 11:
        return f"+{digits}"

    # 10-digit US number without country code
    if len(digits) == 10 and not digits.startswith("0"):
        return f"+1{digits}"

    # Fallback for other unrecognized formats
    return digits


def clean_company_name(name: str) -> str | None:
    """Strip legal suffixes from a company name and validate length; return None on failure."""
    if not name:
        return None
    cleaned = re.sub(r"(?i)\b(inc|llc|ltd|corp)\b\.?", "", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not (2 <= len(cleaned) <= 50):
        return None
    if cleaned.lower() in settings.JUNK_NAMES:
        return None
    return cleaned
