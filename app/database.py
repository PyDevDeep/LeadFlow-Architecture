import sqlite3
from contextlib import contextmanager

from app.config import settings


@contextmanager
def get_db_connection():
    """З'єднання з БД через глобальні налаштування"""
    # Використовуємо шлях з нашого єдиного конфігу
    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    query = """
    CREATE TABLE IF NOT EXISTS leads_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        payload TEXT NOT NULL,
        status VARCHAR(20) DEFAULT 'pending',
        retry_count INTEGER DEFAULT 0,
        next_retry_at INTEGER DEFAULT (CAST(strftime('%s', 'now') AS INTEGER))
    );
    """
    try:
        with get_db_connection() as conn:
            conn.execute(query)
            conn.commit()
    except sqlite3.Error as e:
        print(f"DB Initialization Error: {e}")
