import sqlite3
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from app.database import get_db_connection
from app.scraper.client import RequestClient
from app.utils.logger import logger
from app.utils.validators import clean_company_name, clean_phone


def parse_html(html: str) -> dict[str, str]:
    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    name_node = soup.find("h1")
    website_node = soup.find("a", class_="website")
    phone_node = soup.find("span", class_="phone")

    raw_p = phone_node.get_text(strip=True) if isinstance(phone_node, Tag) else ""
    raw_name = name_node.get_text(strip=True) if isinstance(name_node, Tag) else ""
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

    # ВАЛІДАЦІЯ ТА ОЧИЩЕННЯ ДО ЗАПИСУ
    valid_name = clean_company_name(raw_name)
    phone = clean_phone(raw_p)

    if not domain or not valid_name:
        return {}

    return {
        "domain": domain,
        "name": valid_name,
        "website": website,
        "phone": phone,
    }


def push_to_queue(data: dict[str, str]) -> None:
    if not data:
        return

    # INSERT OR IGNORE вирішує проблему дублікатів на рівні бази даних
    query = """
        INSERT OR IGNORE INTO leads_queue (domain, name, website, phone) 
        VALUES (?, ?, ?, ?)
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.execute(
                query, (data["domain"], data["name"], data["website"], data["phone"])
            )
            conn.commit()
            if cursor.rowcount > 0:
                logger.info(f"Новий лід додано в БД: {data['domain']}")
            else:
                logger.debug(f"Дублікат проігноровано базою: {data['domain']}")
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
