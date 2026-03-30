import random
import sqlite3
import time
from typing import Any

import requests

from app.config import settings
from app.database import get_db_connection
from app.utils.logger import logger


def process_batch() -> None:
    """Fetch a batch of pending leads and send them to the webhook."""
    logger.info("Looking for leads to process...")
    leads = get_leads_for_processing(settings.WEBHOOK_BATCH_SIZE)
    if not leads:
        logger.info("Queue is empty.")
        return

    payloads_to_send: list[dict[str, Any]] = []

    for lead in leads:
        formatted_payload: dict[str, Any] = {
            "db_id": lead["id"],
            "domain": lead["domain"],
            "name": lead["name"],
            "website": lead["website"],
            "phone": lead["phone"],
            "description": lead["description"],
            "source_method": lead["source_method"],
        }
        payloads_to_send.append(formatted_payload)

    headers = {
        "x-make-apikey": settings.MAKE_API_KEY,
        "Content-Type": "application/json",
    }

    final_payload: dict[str, Any] = {
        "leads": payloads_to_send,
        "batch_meta": {"count": len(payloads_to_send), "source": "scraper_v1"},
    }

    try:
        response = requests.post(
            settings.WEBHOOK_URL, json=final_payload, headers=headers, timeout=30
        )
        response.raise_for_status()

        for lead in leads:
            update_lead_status(lead["id"], "success")
        logger.info(f"Successfully sent batch of {len(payloads_to_send)} leads.")

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        logger.error(f"HTTP error during send: {status}")

        if status in [429, 500, 502, 503, 504]:
            handle_retry(leads)
        else:
            for lead in leads:
                update_lead_status(lead["id"], "failed")

    except requests.RequestException as e:
        logger.error(f"Network error (timeout/connection): {e}")
        handle_retry(leads)

    except Exception as e:
        logger.critical(f"Critical worker error: {e}", exc_info=True)


def handle_retry(leads: list[dict[str, Any]]) -> None:
    """Schedule leads for retry with exponential backoff, or mark as failed after 5 attempts."""
    current_time = int(time.time())
    for lead in leads:
        new_retry_count = lead["retry_count"] + 1

        if new_retry_count >= 5:
            update_lead_status(lead["id"], "failed", retry_count=new_retry_count)
        else:
            base_delay = (2**new_retry_count) * 5
            jitter = random.randint(1, 15)
            wait_time = base_delay + jitter

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
    """Update the status (and optionally retry metadata) of a lead in the DB."""
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

    try:
        with get_db_connection() as conn:
            conn.execute(query, params)
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"DB Update Error (Lead {lead_id}): {e}")


def get_leads_for_processing(batch_size: int = 50) -> list[dict[str, Any]]:
    """Atomically claim a batch of pending leads and return them for processing."""
    current_time = int(time.time())

    query = """
        UPDATE leads_queue
        SET status = 'processing'
        WHERE id IN (
            SELECT id
            FROM leads_queue
            WHERE status = 'pending' AND next_retry_at <= ?
            ORDER BY id ASC
            LIMIT ?
        )
        RETURNING id, domain, name, website, phone, description, source_method, retry_count;
    """
    try:
        with get_db_connection() as conn:
            rows = conn.execute(query, (current_time, batch_size)).fetchall()
            conn.commit()
            return [dict(row) for row in rows]
    except sqlite3.Error as e:
        logger.error(f"DB Read/Lock Error: {e}")
        return []


if __name__ == "__main__":
    process_batch()
