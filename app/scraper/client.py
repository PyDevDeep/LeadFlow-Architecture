import requests

from app.config import settings


class RequestClient:
    """Ізольований клас для HTTP-запитів."""

    def __init__(self):
        # MVP: звичайний requests із кастомними Headers (User-Agent)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        # TODO: Інтеграція пулу проксі для обходу блокувань

    def fetch_page(self, url: str) -> str:
        """Реалізація методу fetch_page(url)."""
        try:
            response = requests.get(
                url, headers=self.headers, timeout=settings.SCRAPER_TIMEOUT
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Network Error for {url}: {e}")
            return ""
