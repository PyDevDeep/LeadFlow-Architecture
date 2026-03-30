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

    def _is_blacklisted(self, domain: str) -> bool:
        """Перевіряє, чи містить домен заборонені слова з чорного списку"""
        if not domain:
            return True
        return any(bad_domain in domain for bad_domain in settings.DOMAIN_BLACKLIST)

    def _extract_phone_from_text(self, text: str | None) -> str:
        if not text:
            return ""
        match = self.phone_regex.search(text)
        return clean_phone(match.group()) if match else ""

    def _save_lead(
        self,
        domain: str,
        name: str,
        website: str,
        phone: str,
        description: str,
        source_method: str,
    ) -> None:
        """Оновлений метод збереження з жорстким фільтром якості ліда"""
        # Базові структурні вимоги
        if not domain or not name:
            return

        # ЖОРСТКИЙ ФІЛЬТР ЯКОСТІ: Лід має сенс, лише якщо є телефон АБО опис
        if not phone and not description:
            # Використовуємо debug, щоб не спамити консоль мертвими лідами,
            # але мати змогу їх відстежити при потребі
            logger.debug(f"[DB] Лід відхилено (пустий телефон та опис): {domain}")
            return

        query = """
            INSERT OR IGNORE INTO leads_queue (domain, name, website, phone, description, source_method) 
            VALUES (?, ?, ?, ?, ?, ?)
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.execute(
                    query, (domain, name, website, phone, description, source_method)
                )
                conn.commit()
                if cursor.rowcount > 0:
                    logger.info(f"[DB] Новий лід ({source_method}): {domain}")
                else:
                    logger.info(f"[DB] Дублікат проігноровано базою: {domain}")
        except Exception as e:
            logger.error(f"[DB] Помилка збереження {domain}: {e}")

    # --- СЦЕНАРІЙ 1: MAPS ---
    def run_maps_pipeline(self, query: str) -> None:
        logger.info(f"Запуск Maps пайплайну: {query}")
        response = self.client.maps(query)
        places = response.places[: settings.SERPER_MAX_RESULTS]

        for place in places:
            domain = self._extract_domain(place.website or "")

            # ФІЛЬТР ЧОРНОГО СПИСКУ
            if self._is_blacklisted(domain):
                logger.debug(f"[TRACE] Maps пропустив сміттєвий домен: {domain}")
                continue

            name = clean_company_name(place.title)
            phone = clean_phone(place.phoneNumber or "")

            description = place.description or ""

            if domain and name:
                self._save_lead(
                    domain, name, place.website or "", phone, description, "maps"
                )

    # --- СЦЕНАРІЙ 2: SEARCH (Поверхневий збір) ---
    def run_search_pipeline(self, query: str) -> None:
        logger.info(f"Запуск Search пайплайну: {query}")
        response = self.client.search(query)
        organic_results = response.organic[: settings.SERPER_MAX_RESULTS]

        for item in organic_results:
            domain = self._extract_domain(item.link)

            # ФІЛЬТР ЧОРНОГО СПИСКУ
            if self._is_blacklisted(domain):
                logger.debug(f"[TRACE] Search пропустив сміттєвий домен: {domain}")
                continue

            raw_title = item.title.split("-")[0].split("|")[0].strip()[:49]
            name = clean_company_name(raw_title) or domain.split(".")[0].capitalize()
            phone = self._extract_phone_from_text(item.snippet)
            # Беремо сніпет з органічної видачі[cite: 4]
            description = item.snippet or ""

            if domain and name:
                self._save_lead(domain, name, item.link, phone, description, "search")

    # --- СЦЕНАРІЇ 3 та 4: DEEP SCRAPE (Глибокий пошук з пулом потоків) ---
    def run_deep_scrape(
        self,
        targets: list[dict[str, str]],
        source_method: str = "hybrid",
        max_workers: int = settings.SCRAPER_MAX_WORKERS,
    ) -> None:
        """Додано параметр source_method (за замовчуванням hybrid)"""
        logger.info(f"Запуск Deep Scrape ({source_method}) для {len(targets)} цілей")

        def scrape_worker(target: dict[str, str]):
            url = target.get("url", "")
            domain = self._extract_domain(url)

            logger.debug(f"[TRACE] Старт обробки: {domain}")

            if not domain:
                logger.debug(f"[TRACE] Смерть потоку (Пустий домен): {url}")
                return

            # НОВИЙ ЖОРСТКИЙ БЛОК: ЧОРНИЙ СПИСОК
            if self._is_blacklisted(domain):
                logger.debug(
                    f"[TRACE] Смерть потоку (Домен у Чорному списку): {domain}"
                )
                return

            if domain in self.visited_domains:
                logger.debug(
                    f"[TRACE] Смерть потоку (Внутрішній дублікат сесії): {domain}"
                )
                return

            self.visited_domains.add(domain)

            raw_title = (
                (target.get("name") or "").split("-")[0].split("|")[0].strip()[:49]
            )
            name = clean_company_name(raw_title) or domain.split(".")[0].capitalize()

            if not name:
                # ОЦЕ НАЙІМОВІРНІШИЙ ВБИВЦЯ
                logger.debug(
                    f"[TRACE] Смерть потоку (Неможливо згенерувати ім'я): {domain} з сирим '{raw_title}'"
                )
                return

            logger.debug(f"[TRACE] Початок HTTP скрейпінгу: {domain}")
            scrape_resp = self.client.scrape(url)
            text_content = scrape_resp.markdown or scrape_resp.text

            if not text_content:
                logger.warning(
                    f"[TRACE] Serper повернув пустий текст (можливо 500/403 помилка): {domain}"
                )
                return

            phone = self._extract_phone_from_text(text_content)
            description = ""
            if scrape_resp.metadata:
                description = (
                    scrape_resp.metadata.get("Description")
                    or scrape_resp.metadata.get("og:description")
                    or ""
                )

            logger.debug(
                f"[TRACE] Передача в БД: {domain} | Phone: '{phone}' | Desc: '{description[:10]}...'"
            )
            self._save_lead(domain, name, url, phone, description, source_method)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(scrape_worker, t) for t in targets]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Помилка в потоці скрейпінгу: {e}")
