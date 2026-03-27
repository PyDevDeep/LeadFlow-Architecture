import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Конфігурація додатку з .env"""

    # Database
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")

    # API
    api_port: int = int(os.getenv("API_PORT", 8000))
    api_host: str = os.getenv("API_HOST", "127.0.0.1")

    # Scraper
    scraper_timeout: int = int(os.getenv("SCRAPER_TIMEOUT", 30))
    scraper_retries: int = int(os.getenv("SCRAPER_RETRIES", 3))

    # Webhook
    webhook_url: str = os.getenv("WEBHOOK_URL", "")
    webhook_batch_size: int = int(os.getenv("WEBHOOK_BATCH_SIZE", 10))

    # Logger
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
