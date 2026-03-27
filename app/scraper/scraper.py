import json
import sqlite3

from bs4 import BeautifulSoup, Tag

from app.database import get_db_connection, init_db


def parse_html(html: str) -> dict[str, str]:
    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    name_node = soup.find("h1")
    website_node = soup.find("a", class_="website")
    phone_node = soup.find("span", class_="phone")

    return {
        "name": name_node.text.strip() if isinstance(name_node, Tag) else "Unknown",
        "website": str(website_node.get("href", ""))
        if isinstance(website_node, Tag)
        else "",
        "phone": phone_node.text.strip() if isinstance(phone_node, Tag) else "",
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
