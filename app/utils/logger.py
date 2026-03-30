import logging
import os
from logging.handlers import RotatingFileHandler

# Create the log directory at the project root
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")

# Shared formatter for all handlers
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# --- 1. FILE HANDLER (full audit trail) ---
# Rotation: max 5 MB per file, keep 3 previous copies
file_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
file_handler.setFormatter(formatter)
# Write DEBUG and above to file so crash traces are always available
file_handler.setLevel(logging.DEBUG)

# --- 2. CONSOLE HANDLER (operational monitoring) ---
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
# Only show INFO and above on the console
console_handler.setLevel(logging.INFO)

# --- LOGGER INITIALIZATION ---
logger = logging.getLogger("scraper_app")
# Logger level must be the lowest so all records reach the handlers
logger.setLevel(logging.DEBUG)

# Avoid duplicate handlers on repeated module imports
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
