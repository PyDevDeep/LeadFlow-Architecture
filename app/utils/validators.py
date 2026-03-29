import re

from app.config import settings


def clean_phone(raw_phone: str) -> str:
    """Універсальна нормалізація телефонного номера."""
    if not raw_phone:
        return ""

    # Залишаємо тільки цифри та плюс
    digits = re.sub(r"[^\d+]", "", raw_phone)

    # Якщо номер вже має коректний міжнародний формат
    if digits.startswith("+"):
        return digits

    # Нормалізація українських (відсутній плюс або починається з 0)
    if digits.startswith("380") and len(digits) == 12:
        return f"+{digits}"
    if digits.startswith("0") and len(digits) == 10:
        return f"+38{digits}"

    # Нормалізація американських (відсутній плюс)
    if digits.startswith("1") and len(digits) == 11:
        return f"+{digits}"

    # Якщо номер 10-значний американський (без 1 на початку)
    if len(digits) == 10 and not digits.startswith("0"):
        return f"+1{digits}"

    # Фолбек для інших невідомих форматів
    return digits


def clean_company_name(name: str) -> str | None:
    """Очищення назви компанії. Повертає None при провалі валідації."""
    if not name:
        return None
    cleaned = re.sub(r"(?i)\b(inc\.?|llc|ltd\.?|corp\.?)\b", "", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not (2 <= len(cleaned) <= 50):
        return None
    if cleaned.lower() in settings.JUNK_NAMES:
        return None
    return cleaned
