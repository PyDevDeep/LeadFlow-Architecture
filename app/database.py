import sqlite3
from contextlib import contextmanager

from app.config import settings
from app.utils.logger import logger


@contextmanager
def get_db_connection():
    """Yield a SQLite connection with WAL mode enabled, closing it on exit."""
    # Hard timeout for multithreaded access
    conn = sqlite3.connect(settings.DATABASE_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # Enable Write-Ahead Logging for concurrent access
    conn.execute("pragma journal_mode=wal")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Create the leads_queue table if it does not exist."""
    query = """
    CREATE TABLE IF NOT EXISTS leads_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain VARCHAR(255) UNIQUE NOT NULL,
        name VARCHAR(255) NOT NULL,
        website VARCHAR(255),
        phone VARCHAR(50),
        description TEXT,
        source_method VARCHAR(50),
        status VARCHAR(20) DEFAULT 'pending',
        retry_count INTEGER DEFAULT 0,
        next_retry_at INTEGER DEFAULT (CAST(strftime('%s', 'now') AS INTEGER))
    );
    """
    try:
        with get_db_connection() as conn:
            conn.execute(query)
            conn.commit()
            logger.info("DB schema initialized. UNIQUE constraint applied to domain.")
    except sqlite3.Error as e:
        logger.error(f"DB Initialization Error: {e}", exc_info=True)
