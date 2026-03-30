import logging
import os
from logging.handlers import RotatingFileHandler

# Створюємо директорію для логів на рівні проекту
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")

# Єдиний формат для всіх виводів
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# --- 1. ФАЙЛОВИЙ ХЕНДЛЕР (Глибокий аудит) ---
# Ротація: макс 5 МБ на файл, зберігаємо 3 попередні копії
file_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
file_handler.setFormatter(formatter)
# У файл ЗАВЖДИ пишемо DEBUG, щоб мати історію трасування при падіннях
file_handler.setLevel(logging.DEBUG)

# --- 2. КОНСОЛЬНИЙ ХЕНДЛЕР (Оперативний моніторинг) ---
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
# У консоль виводимо тільки INFO, WARNING, ERROR, CRITICAL
console_handler.setLevel(logging.INFO)

# --- ІНІЦІАЛІЗАЦІЯ ЛОГЕРА ---
logger = logging.getLogger("scraper_app")
# Загальний рівень логера має бути найнижчим, щоб пропускати все до хендлерів
logger.setLevel(logging.DEBUG)

# Уникаємо дублювання хендлерів при повторних імпортах модуля
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
