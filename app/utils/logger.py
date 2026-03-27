import logging
from app.config import settings


def setup_logger(name: str = __name__) -> logging.Logger:
    """
    Налаштувати логер

    Args:
        name: Ім'я логера

    Returns:
        Налаштований логер
    """
    logger = logging.getLogger(name)
    logger.setLevel(settings.LOG_LEVEL)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logger(__name__)
