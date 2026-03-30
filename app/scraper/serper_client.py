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
    """Isolated client for interacting with the serper.dev API."""

    BASE_URL = "https://google.serper.dev"
    SCRAPE_URL = "https://scrape.serper.dev"

    def __init__(self):
        """Initialize the client and warn if the API key is missing."""
        if not settings.SERPER_API_KEY:
            logger.critical("SERPER_API_KEY not found in configuration!")

        self.headers = {
            "X-API-KEY": settings.SERPER_API_KEY,
            "Content-Type": "application/json",
        }

    def maps(self, query: str) -> SerperMapsResponse:
        """Search Google Maps and return local businesses with phone numbers."""
        payload: dict[str, Any] = {"q": query, "num": settings.SERPER_MAX_RESULTS}
        try:
            response = requests.post(
                f"{self.BASE_URL}/maps", headers=self.headers, json=payload, timeout=15
            )
            response.raise_for_status()
            return SerperMapsResponse.model_validate(response.json())
        except Exception as e:
            logger.error(f"Serper Maps error for '{query}': {e}")
            return SerperMapsResponse()

    def search(self, query: str) -> SerperSearchResponse:
        """Fetch organic search results for link generation."""
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
            logger.error(f"Serper Search error for '{query}': {e}")
            return SerperSearchResponse()

    def scrape(self, url: str) -> SerperScrapeResponse:
        """Extract text content from a web page."""
        payload: dict[str, Any] = {"url": url}
        try:
            response = requests.post(
                self.SCRAPE_URL, headers=self.headers, json=payload, timeout=60
            )
            response.raise_for_status()
            return SerperScrapeResponse.model_validate(response.json())
        except Exception as e:
            logger.error(f"Serper Scrape error for '{url}': {e}")
            return SerperScrapeResponse()
