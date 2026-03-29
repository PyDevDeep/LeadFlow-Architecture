import re

JUNK_NAMES = {"home", "welcome", "untitled", "index", "test"}


def clean_phone(raw_phone: str) -> str:
    """Нормалізація телефонного номера."""
    if not raw_phone:
        return ""
    digits = re.sub(r"[^\d+]", "", raw_phone)
    if digits.startswith("0") and len(digits) == 10:
        return f"+38{digits}"
    if digits.startswith("380") and len(digits) == 12:
        return f"+{digits}"
    return digits


def clean_company_name(name: str) -> str | None:
    """Очищення назви компанії. Повертає None при провалі валідації."""
    if not name:
        return None
    cleaned = re.sub(r"(?i)\b(inc\.?|llc|ltd\.?|corp\.?)\b", "", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not (2 <= len(cleaned) <= 50):
        return None
    if cleaned.lower() in JUNK_NAMES:
        return None
    return cleaned
