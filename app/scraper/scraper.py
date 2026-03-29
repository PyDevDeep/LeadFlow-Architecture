import json
import sqlite3
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from app.database import get_db_connection
from app.scraper.client import RequestClient
from app.utils.logger import logger
from app.utils.validators import clean_phone


def parse_html(html: str) -> dict[str, str]:
    if not html:
        return {"name": "", "website": "", "domain": "", "phone": ""}

    soup = BeautifulSoup(html, "html.parser")
    name_node = soup.find("h1")
    website_node = soup.find("a", class_="website")
    phone_node = soup.find("span", class_="phone")

    raw_p = phone_node.get_text(strip=True) if isinstance(phone_node, Tag) else ""
    phone = clean_phone(raw_p)

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
        "phone": phone,
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
        logger.error(f"DB Insert Error: {e}")


def run_scraper(url: str) -> None:
    """Точка входу для CLI."""
    logger.info(f"Запуск скрейпінгу для: {url}")
    client = RequestClient()
    html = client.fetch_page(url)

    if not html:
        logger.warning(f"Отримано порожню сторінку: {url}")
        return

    data = parse_html(html)
    if data.get("name"):
        push_to_queue(data)
        logger.info(f"Успішно додано в чергу: {data.get('domain')}")
    else:
        logger.warning(f"Не знайдено валідної назви компанії на {url}")
