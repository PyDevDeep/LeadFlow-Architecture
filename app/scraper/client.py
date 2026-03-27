from typing import Any, Optional

import requests

from app.config import settings
from app.utils.logger import logger


class RequestClient:
    """HTTP клієнт для скрейпінгу"""

    def __init__(self, timeout: int = 10, retries: int = 10):
        self.timeout = timeout or settings.scraper_timeout
        self.retries = retries or settings.scraper_retries
        self.session = requests.Session()

    def get(self, url: str, **kwargs: Any) -> Optional[requests.Response]:
        """
        GET запит з обробкою помилок та повторних спроб

        Args:
            url: URL для запиту
            **kwargs: Додаткові аргументи для requests

        Returns:
            Response об'єкт або None при помилці
        """
        for attempt in range(self.retries):
            try:
                response = self.session.get(url, timeout=self.timeout, **kwargs)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{self.retries} failed for {url}: {e}"
                )
                if attempt == self.retries - 1:
                    logger.error(f"Failed to fetch {url} after {self.retries} retries")
                    return None
        return None

    def close(self):
        """Закрити сесію"""
        self.session.close()
