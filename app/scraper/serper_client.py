from typing import Any

import requests

from app.config import settings
from app.schemas.serper import (
    SerperMapsResponse,
    SerperScrapeResponse,
    SerperSearchResponse,
)
from app.utils.logger import logger


class SerperClient:
    """Ізольований клієнт для взаємодії з API serper.dev"""

    BASE_URL = "https://google.serper.dev"
    SCRAPE_URL = "https://scrape.serper.dev"

    def __init__(self):
        if not settings.SERPER_API_KEY:
            logger.critical("SERPER_API_KEY не знайдено в конфігурації!")

        self.headers = {
            "X-API-KEY": settings.SERPER_API_KEY,
            "Content-Type": "application/json",
        }

    def maps(self, query: str) -> SerperMapsResponse:
        """Пошук по Google Maps. Повертає локальні бізнеси з телефонами."""
        payload: dict[str, Any] = {"q": query, "num": settings.SERPER_MAX_RESULTS}
        try:
            response = requests.post(
                f"{self.BASE_URL}/maps", headers=self.headers, json=payload, timeout=15
            )
            response.raise_for_status()
            return SerperMapsResponse.model_validate(response.json())
        except Exception as e:
            logger.error(f"Помилка Serper Maps для '{query}': {e}")
            return SerperMapsResponse()

    def search(self, query: str) -> SerperSearchResponse:
        """Органічна видача. Використовувати для генерації посилань."""
        payload: dict[str, Any] = {"q": query, "num": settings.SERPER_MAX_RESULTS}
        try:
            response = requests.post(
                f"{self.BASE_URL}/search",
                headers=self.headers,
                json=payload,
                timeout=15,
            )
            response.raise_for_status()
            return SerperSearchResponse.model_validate(response.json())
        except Exception as e:
            logger.error(f"Помилка Serper Search для '{query}': {e}")
            return SerperSearchResponse()

    def scrape(self, url: str) -> SerperScrapeResponse:
        """Витягування контенту зі сторінки."""
        payload: dict[str, Any] = {"url": url}
        try:
            response = requests.post(
                self.SCRAPE_URL, headers=self.headers, json=payload, timeout=30
            )
            response.raise_for_status()
            return SerperScrapeResponse.model_validate(response.json())
        except Exception as e:
            logger.error(f"Помилка Serper Scrape для '{url}': {e}")
            return SerperScrapeResponse()
