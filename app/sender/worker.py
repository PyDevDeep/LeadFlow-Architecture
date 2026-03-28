import json
import random
import re
import sqlite3
import time
from typing import Any

import requests

from app.config import settings
from app.database import get_db_connection

# Чорний список сміттєвих слів (у нижньому регістрі для порівняння)
JUNK_NAMES = {"home", "welcome", "untitled", "index", "test"}


def clean_company_name(name: str) -> str | None:
    """Очищає назву компанії та повертає None, якщо вона не пройшла валідацію."""
    if not name:
        return None

    # Sanitization: видаляємо поширені суфікси (Inc, LLC тощо) незалежно від регістру
    cleaned = re.sub(r"(?i)\b(inc\.?|llc|ltd\.?|corp\.?)\b", "", name)

    # Видаляємо множинні пробіли та обрізаємо краї
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Length Check: відсіюємо занадто короткі або довгі назви
    if not (2 <= len(cleaned) <= 50):
        return None

    # Junk Filter: перевірка на повний збіг зі сміттєвими словами
    if cleaned.lower() in JUNK_NAMES:
        return None

    return cleaned


def process_batch() -> None:
    leads = get_leads_for_processing(settings.WEBHOOK_BATCH_SIZE)
    if not leads:
        return

    unique_domains: set[str] = set()
    unique_leads: list[dict[str, Any]] = []
    payloads_to_send: list[dict[str, Any]] = []

    for lead in leads:
        try:
            payload = json.loads(lead["payload"])
        except json.JSONDecodeError:
            update_lead_status(lead["id"], "invalid_data")
            continue

        domain = payload.get("domain")

        # ЗАСТОСУВАННЯ ФІЛЬТРА
        valid_name = clean_company_name(payload.get("name", ""))

        # Відсіюємо записи без домену або з некоректною назвою компанії
        if not domain or not valid_name:
            update_lead_status(lead["id"], "invalid_data")
            continue

        if domain in unique_domains:
            update_lead_status(lead["id"], "duplicate")
            continue

        unique_domains.add(domain)
        unique_leads.append(lead)

        # Формуємо фінальний об'єкт з уже очищеною назвою (valid_name)
        formatted_payload: dict[str, Any] = {
            "db_id": lead["id"],
            "domain": domain,
            "name": valid_name,
            "website": payload.get("website", ""),
            "phone": payload.get("phone", ""),
        }
        payloads_to_send.append(formatted_payload)

    # ВИПРАВЛЕНО ВІДСТУПИ: винесено за межі циклу for
    if not payloads_to_send:
        return

    # Формуємо заголовки для авторизації на make.com
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
            settings.WEBHOOK_URL,
            json=final_payload,  # <--- ВІДПРАВЛЯЄМО ОНОВЛЕНУ СТРУКТУРУ
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()

        # Якщо все ок:
        for lead in unique_leads:
            update_lead_status(lead["id"], "success")

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        if status in [429, 500, 502, 503, 504]:
            handle_retry(unique_leads)
        else:
            for lead in unique_leads:
                update_lead_status(lead["id"], "failed")
    except requests.RequestException:  # Timeout, ConnectionError
        handle_retry(unique_leads)
    except Exception as e:
        print(f"Критична помилка воркера: {e}")
        # Тут можна додати логіку повернення лідів у pending,
        # але треба бути обережним з нескінченними циклами


def handle_retry(leads: list[dict[str, Any]]) -> None:
    """Реалізація Exponential Backoff + Full Jitter."""
    current_time = int(time.time())
    for lead in leads:
        new_retry_count = lead["retry_count"] + 1

        if new_retry_count >= 5:
            update_lead_status(lead["id"], "failed", retry_count=new_retry_count)
        else:
            # Базова затримка: 2^retry * 5. Jitter: додаємо випадкові 1-15 секунд
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
        print(f"DB Update Error (Lead {lead_id}): {e}")


def get_leads_for_processing(batch_size: int = 50) -> list[dict[str, Any]]:
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
        RETURNING id, payload, retry_count;
    """
    try:
        with get_db_connection() as conn:
            rows = conn.execute(query, (current_time, batch_size)).fetchall()
            conn.commit()
            return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"DB Read/Lock Error: {e}")
        return []


if __name__ == "__main__":
    # Точка входу для запуску воркера
    process_batch()
