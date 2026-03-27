# app/sender/worker.py

from datetime import datetime
from typing import Any, List, Sequence

import requests
from sqlalchemy.orm import Session

from app.config import settings
from app.models import LEEDData
from app.utils.logger import logger


class WebhookWorker:
    def __init__(self, webhook_url: str = "", batch_size: int = 10):
        self.webhook_url = webhook_url or settings.webhook_url
        self.batch_size = batch_size or settings.webhook_batch_size

    def send_batch(self, db: Session, batch_ids: Sequence[int]) -> bool:
        if not self.webhook_url:
            logger.error("Webhook URL not configured")
            return False

        try:
            # Використовуємо .filter() з правильним синтаксисом
            records = db.query(LEEDData).filter(LEEDData.id.in_(batch_ids)).all()

            payload: List[dict[str, Any]] = [
                {
                    "id": r.id,
                    "title": r.title,
                    "description": r.description,
                    "url": r.url,
                }
                for r in records
            ]

            response = requests.post(
                self.webhook_url, json=payload, timeout=settings.scraper_timeout
            )
            response.raise_for_status()

            for record in records:
                # Type ignore потрібен, якщо моделі не використовують Mapped[] (SQLAlchemy 2.0)
                record.is_sent = True  # type: ignore
                record.sent_at = datetime.utcnow()  # type: ignore
            db.commit()

            logger.info(f"Successfully sent {len(batch_ids)} records")
            return True

        except requests.RequestException as e:
            logger.error(f"Failed to send: {e}")
            return False

    def process_pending(self, db: Session) -> None:
        # Виправлено Ruff E712: використовуємо .is_(False)
        pending = (
            db.query(LEEDData)
            .filter(LEEDData.is_sent.is_(False))
            .limit(self.batch_size)
            .all()
        )

        if not pending:
            return

        # Явне приведення до int для Pylance
        batch_ids: List[int] = [int(r.id) for r in pending]
        self.send_batch(db, batch_ids)
