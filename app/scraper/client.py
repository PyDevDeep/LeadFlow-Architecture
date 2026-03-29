import requests

from app.config import settings
from app.utils.logger import logger


class RequestClient:
    """Ізольований клас для HTTP-запитів."""

    def __init__(self):
        # MVP: звичайний requests із кастомними Headers (User-Agent)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        # TODO: Інтеграція пулу проксі для обходу блокувань

    def fetch_page(self, url: str) -> str:
        try:
            response = requests.get(
                url, headers=self.headers, timeout=settings.SCRAPER_TIMEOUT
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Network Error for {url}: {e}")
            return ""
