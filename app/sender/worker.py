import json
import time
from typing import Any

import requests

from app.config import settings
from app.database import get_db_connection


def process_batch() -> None:
    leads = get_leads_for_processing(settings.WEBHOOK_BATCH_SIZE)
    print(f"DEBUG: Found {len(leads)} leads to process")
    if not leads:
        return

    # Формування батчу: десеріалізація JSON-рядків у список об'єктів
    payloads = [json.loads(lead["payload"]) for lead in leads]

    try:
        response = requests.post(settings.WEBHOOK_URL, json=payloads, timeout=30)

        if response.status_code == 200:
            for lead in leads:
                update_lead_status(lead["id"], "success")
        elif response.status_code in [429, 500, 502, 503, 504]:
            handle_retry(leads)
        else:
            # Інші помилки (400, 404 тощо) зазвичай не потребують повтору
            for lead in leads:
                update_lead_status(lead["id"], "failed")

    except requests.RequestException:
        handle_retry(leads)


def handle_retry(leads: list[dict[str, Any]]) -> None:
    """Реалізація Exponential Backoff: T = 2^retry * 5."""
    current_time = int(time.time())
    for lead in leads:
        new_retry_count = lead["retry_count"] + 1

        if new_retry_count >= 5:
            update_lead_status(lead["id"], "failed", retry_count=new_retry_count)
        else:
            # Розрахунок затримки: 2^retry * 5
            wait_time = (2**new_retry_count) * 5
            next_retry = current_time + wait_time
            update_lead_status(
                lead["id"],
                "pending",
                retry_count=new_retry_count,
                next_retry=next_retry,
            )


def update_lead_status(
    lead_id: int,
    status: str,
    retry_count: int | None = None,
    next_retry: int | None = None,
) -> None:
    """Оновлення фінального або проміжного стану ліда в БД."""
    query = "UPDATE leads_queue SET status = ?"
    params: list[Any] = [status]

    if retry_count is not None:
        query += ", retry_count = ?"
        params.append(retry_count)
    if next_retry is not None:
        query += ", next_retry_at = ?"
        params.append(next_retry)

    query += " WHERE id = ?"
    params.append(lead_id)

    with get_db_connection() as conn:
        conn.execute(query, params)
        conn.commit()


def get_leads_for_processing(batch_size: int = 50) -> list[dict[str, Any]]:
    current_time = int(time.time())

    with get_db_connection() as conn:
        conn.execute("BEGIN EXCLUSIVE;")

        rows = conn.execute(
            """
            SELECT id, payload, retry_count 
            FROM leads_queue 
            WHERE status = 'pending' AND next_retry_at <= ? 
            ORDER BY id ASC -- Додано для чіткої послідовності 
            LIMIT ?
            """,
            (current_time, batch_size),
        ).fetchall()

        if not rows:
            conn.commit()
            return []

        ids = [row["id"] for row in rows]
        placeholders = ",".join("?" * len(ids))

        conn.execute(
            f"UPDATE leads_queue SET status = 'processing' WHERE id IN ({placeholders})",
            ids,
        )
        conn.commit()

        return [dict(row) for row in rows]


if __name__ == "__main__":
    # Точка входу для запуску воркера
    process_batch()
