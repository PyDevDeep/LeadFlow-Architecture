import json
import re
import sqlite3
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from app.database import get_db_connection, init_db


def clean_phone(raw_phone: str) -> str:
    if not raw_phone:
        return ""

    # 1. Видаляємо все, крім цифр та плюса
    digits = re.sub(r"[^\d+]", "", raw_phone)

    # 2. Якщо номер починається з 0 (н-р 044...), додаємо +38
    if digits.startswith("0") and len(digits) == 10:
        return f"+38{digits}"

    # 3. Якщо починається з 380 (без плюса)
    if digits.startswith("380") and len(digits) == 12:
        return f"+{digits}"

    return digits


def parse_html(html: str) -> dict[str, str]:
    if not html:
        return {"name": "", "website": "", "domain": "", "phone": ""}

    soup = BeautifulSoup(html, "html.parser")

    # Шукаємо вузли
    name_node = soup.find("h1")
    website_node = soup.find("a", class_="website")
    phone_node = soup.find("span", class_="phone")  # <--- ЦЕ БУЛО ПРОПУЩЕНО

    # Обробка телефону
    raw_p = phone_node.get_text(strip=True) if isinstance(phone_node, Tag) else ""
    phone = clean_phone(raw_p)

    # Обробка сайту
    website = (
        str(website_node.get("href", "")).strip()
        if isinstance(website_node, Tag)
        else ""
    )

    domain = ""
    if website and not website.startswith(("mailto:", "tel:", "/", "#")):
        clean_url = (
            website
            if website.startswith(("http://", "https://"))
            else f"http://{website}"
        )
        domain = urlparse(clean_url).netloc.removeprefix("www.")

    return {
        "name": name_node.get_text(strip=True) if isinstance(name_node, Tag) else "",
        "website": website,
        "domain": domain,
        "phone": phone,  # <--- ПОВЕРТАЄМО ВЖЕ ОЧИЩЕНИЙ ТЕЛЕФОН
    }


def push_to_queue(payload: dict[str, str]) -> None:
    if not payload.get("name"):
        return

    query = "INSERT INTO leads_queue (payload) VALUES (?)"
    try:
        with get_db_connection() as conn:
            conn.execute(query, (json.dumps(payload),))
            conn.commit()
    except sqlite3.Error as e:
        print(f"DB Insert Error: {e}")


if __name__ == "__main__":
    init_db()

    mock_html = """
    <html>
        <h1>Test Company</h1>
        <a class="website" href="https://test.com">Website</a>
        <span class="phone">+380000000000</span>
    </html>
    """

    for _ in range(50):
        data = parse_html(mock_html)
        push_to_queue(data)

    print("Producer finished. Дані завантажено.")
