from typing import Any

from pydantic import BaseModel


class SerperMapItem(BaseModel):
    """A single place result from the Serper Maps API."""

    title: str
    address: str | None = None
    phoneNumber: str | None = None
    website: str | None = None
    description: str | None = None


class SerperSearchItem(BaseModel):
    """A single organic result from the Serper Search API."""

    title: str
    link: str
    snippet: str | None = None


class SerperScrapeResponse(BaseModel):
    """Response from the Serper Scrape API."""

    text: str | None = None
    markdown: str | None = None
    metadata: dict[str, Any] | None = None


class SerperMapsResponse(BaseModel):
    """Top-level response wrapper for Maps API results."""

    places: list[SerperMapItem] = []


class SerperSearchResponse(BaseModel):
    """Top-level response wrapper for Search API results."""

    organic: list[SerperSearchItem] = []
