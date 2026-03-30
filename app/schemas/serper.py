from typing import Any

from pydantic import BaseModel


class SerperMapItem(BaseModel):
    title: str
    address: str | None = None
    phoneNumber: str | None = None
    website: str | None = None
    description: str | None = None


class SerperSearchItem(BaseModel):
    title: str
    link: str
    snippet: str | None = None


class SerperScrapeResponse(BaseModel):
    text: str | None = None
    markdown: str | None = None
    metadata: dict[str, Any] | None = None


class SerperMapsResponse(BaseModel):
    places: list[SerperMapItem] = []


class SerperSearchResponse(BaseModel):
    organic: list[SerperSearchItem] = []
