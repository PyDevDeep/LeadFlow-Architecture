from typing import Optional, List
from bs4 import BeautifulSoup

from app.utils.logger import logger


class LEEDParser:
    """Парсер для LEED даних"""

    @staticmethod
    def parse_html(html: str) -> Optional[dict[str, str | None]]:
        """
        Парсити HTML та витягти LEED дані

        Args:
            html: HTML вміст

        Returns:
            Словник з витягнутими даними або None
        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Приклад парсингу - адаптуй під свою структуру
            title = soup.find("h1")
            description = soup.find("p")

            if not title:
                logger.warning("Title not found in HTML")
                return None

            return {
                "title": title.get_text(strip=True),
                "description": description.get_text(strip=True)
                if description
                else None,
            }
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return None

    @staticmethod
    def extract_urls(html: str) -> List[str]:
        """
        Витягти всі URL з HTML

        Args:
            html: HTML вміст

        Returns:
            Список URL адрес
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            urls = [a.get("href") for a in soup.find_all("a") if a.get("href")]
            return urls
        except Exception as e:
            logger.error(f"Error extracting URLs: {e}")
            return []
