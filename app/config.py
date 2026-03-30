import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Simple configuration via os.getenv (MVP style)."""

    # Database
    DATABASE_PATH = os.getenv("DATABASE_PATH", "leads.db")

    # Scraper
    SCRAPER_TIMEOUT = int(os.getenv("SCRAPER_TIMEOUT", 30))
    SCRAPER_RETRIES = int(os.getenv("SCRAPER_RETRIES", 3))
    SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
    # Concurrency limits
    SCRAPER_MAX_WORKERS = int(os.getenv("SCRAPER_MAX_WORKERS", 3))
    SERPER_MAX_RESULTS = int(os.getenv("SERPER_MAX_RESULTS", 5))
    # Webhook
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
    WEBHOOK_BATCH_SIZE = int(os.getenv("WEBHOOK_BATCH_SIZE", default=10))
    MAKE_API_KEY = os.getenv("MAKE_LEAD_KEY", "")
    # Logger
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # --- REGEX PROFILES ---
    REGEX_PHONE_UA = r"(?:\+?380|0)\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}"
    REGEX_PHONE_US = r"(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}"

    # Active pattern used by ScrapeManager
    ACTIVE_PHONE_REGEX = REGEX_PHONE_UA
    JUNK_NAMES = {"home", "welcome", "untitled", "index", "test"}

    # Hard domain blacklist (aggregators, social media, blogs)
    DOMAIN_BLACKLIST = {
        "medium.com",
        "linkedin.com",
        "dou.ua",
        "clutch.co",
        "designrush.com",
        "sortlist.com",
        "ahrefs.com",
        "themanifest.com",
        "goodfirms.co",
        "upwork.com",
        "facebook.com",
        "instagram.com",
        "twitter.com",
        "github.com",
        "techbehemoths.com",
        "agencyvista.com",
    }


settings = Settings()
