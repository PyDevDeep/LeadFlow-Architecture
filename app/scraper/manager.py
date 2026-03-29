import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from app.config import settings
from app.database import get_db_connection
from app.scraper.serper_client import SerperClient
from app.utils.logger import logger
from app.utils.validators import clean_company_name, clean_phone


class ScrapeManager:
    """Оркестратор процесів лідогенерації"""

    def __init__(self):
        self.client = SerperClient()
        self.visited_domains: set[str] = set()

        try:
            self.phone_regex = re.compile(settings.ACTIVE_PHONE_REGEX)
        except re.error as e:
            logger.critical(f"Помилка компіляції ACTIVE_PHONE_REGEX: {e}")
            raise SystemExit("Невалідний регулярний вираз у конфігурації.")

    def _extract_domain(self, url: str) -> str:
        if not url:
            return ""
        clean_url = url if url.startswith(("http://", "https://")) else f"http://{url}"
        return urlparse(clean_url).netloc.removeprefix("www.")

    def _extract_phone_from_text(self, text: str | None) -> str:
        if not text:
            return ""
        match = self.phone_regex.search(text)
        return clean_phone(match.group()) if match else ""

    def _save_lead(self, domain: str, name: str, website: str, phone: str) -> None:
        if not domain or not name:
            return

        query = """
            INSERT OR IGNORE INTO leads_queue (domain, name, website, phone) 
            VALUES (?, ?, ?, ?)
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.execute(query, (domain, name, website, phone))
                conn.commit()
                if cursor.rowcount > 0:
                    logger.info(f"[DB] Новий лід: {domain} | {phone}")
        except Exception as e:
            logger.error(f"[DB] Помилка збереження {domain}: {e}")

    # --- СЦЕНАРІЙ 1: MAPS (Найбільш ефективний) ---
    def run_maps_pipeline(self, query: str) -> None:
        logger.info(f"Запуск Maps пайплайну: {query}")
        response = self.client.maps(query)

        for place in response.places:
            domain = self._extract_domain(place.website or "")
            name = clean_company_name(place.title)
            phone = clean_phone(place.phoneNumber or "")

            if domain and name:
                self._save_lead(domain, name, place.website or "", phone)

    # --- СЦЕНАРІЙ 2: SEARCH (Поверхневий збір) ---
    def run_search_pipeline(self, query: str) -> None:
        logger.info(f"Запуск Search пайплайну: {query}")
        response = self.client.search(query)

        for item in response.organic:
            domain = self._extract_domain(item.link)
            name = clean_company_name(item.title)
            phone = self._extract_phone_from_text(item.snippet)

            if domain and name:
                self._save_lead(domain, name, item.link, phone)

    # --- СЦЕНАРІЇ 3 та 4: DEEP SCRAPE (Глибокий пошук з пулом потоків) ---
    def run_deep_scrape(
        self, targets: list[dict[str, str]], max_workers: int = 5
    ) -> None:
        """
        Очікує список словників: [{"url": "...", "name": "... (опціонально)"}]
        """
        logger.info(
            f"Запуск Deep Scrape для {len(targets)} цілей ({max_workers} потоків)"
        )

        def scrape_worker(target: dict[str, str]):
            url = target.get("url", "")
            domain = self._extract_domain(url)

            # Дедуплікація в оперативній пам'яті до виклику API
            if not domain or domain in self.visited_domains:
                return
            self.visited_domains.add(domain)

            # Синтезуємо назву, якщо вона відсутня (для TXT файлів)
            raw_name = target.get("name") or domain.split(".")[0].capitalize()
            name = clean_company_name(raw_name)
            if not name:
                return

            # Звернення до API
            scrape_resp = self.client.scrape(url)
            text_content = scrape_resp.markdown or scrape_resp.text

            phone = self._extract_phone_from_text(text_content)
            self._save_lead(domain, name, url, phone)

        # Конкурентне виконання з блокуванням падінь
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(scrape_worker, t) for t in targets]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Помилка в потоці скрейпінгу: {e}")
