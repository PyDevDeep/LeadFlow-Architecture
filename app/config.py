import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Проста конфігурація через os.getenv (MVP Style)"""

    # Database
    # Змінюємо database_url на шлях до файлу для sqlite3
    DATABASE_PATH = os.getenv("DATABASE_PATH", "leads.db")

    # Scraper
    SCRAPER_TIMEOUT = int(os.getenv("SCRAPER_TIMEOUT", 30))
    SCRAPER_RETRIES = int(os.getenv("SCRAPER_RETRIES", 3))

    # Webhook
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
    WEBHOOK_BATCH_SIZE = int(os.getenv("WEBHOOK_BATCH_SIZE", default=10))
    # Додаємо зчитування токена
    MAKE_API_KEY = os.getenv("MAKE_LEAD_KEY", "")
    # Logger
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


# Створюємо екземпляр для імпорту в інші модулі
settings = Settings()
