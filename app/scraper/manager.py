import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from app.config import settings
from app.database import get_db_connection
from app.scraper.serper_client import SerperClient
from app.utils.logger import logger
from app.utils.validators import clean_company_name, clean_phone


class ScrapeManager:
    """Orchestrator for lead generation pipelines."""

    def __init__(self):
        self.client = SerperClient()
        self.visited_domains: set[str] = set()

        try:
            self.phone_regex = re.compile(settings.ACTIVE_PHONE_REGEX)
        except re.error as e:
            logger.critical(f"Failed to compile ACTIVE_PHONE_REGEX: {e}")
            raise SystemExit("Invalid regex in configuration.") from e

    def _extract_domain(self, url: str) -> str:
        """Extract the bare domain (no www) from a URL."""
        if not url:
            return ""
        clean_url = url if url.startswith(("http://", "https://")) else f"http://{url}"
        return urlparse(clean_url).netloc.removeprefix("www.")

    def _is_blacklisted(self, domain: str) -> bool:
        """Return True if the domain matches any entry in the blacklist."""
        if not domain:
            return True
        return any(bad_domain in domain for bad_domain in settings.DOMAIN_BLACKLIST)

    def _extract_phone_from_text(self, text: str | None) -> str:
        """Search text for a phone number and return it normalized, or empty string."""
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
        """Persist a lead to the DB, rejecting entries with no phone and no descript"""
        if not domain or not name:
            return

        # A lead is only useful if it has a phone or a description
        if not phone and not description:
            logger.debug(f"[DB] Lead rejected (no phone or description): {domain}")
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
                    logger.info(f"[DB] New lead ({source_method}): {domain}")
                else:
                    logger.info(f"[DB] Duplicate ignored by DB: {domain}")
        except Exception as e:
            logger.error(f"[DB] Save error for {domain}: {e}")

    # --- PIPELINE 1: MAPS ---
    def run_maps_pipeline(self, query: str) -> None:
        """Run the Maps pipeline: fetch local businesses and save as leads."""
        logger.info(f"Starting Maps pipeline: {query}")
        response = self.client.maps(query)
        places = response.places[: settings.SERPER_MAX_RESULTS]

        for place in places:
            domain = self._extract_domain(place.website or "")

            if self._is_blacklisted(domain):
                logger.debug(f"[TRACE] Maps skipped blacklisted domain: {domain}")
                continue

            name = clean_company_name(place.title)
            phone = clean_phone(place.phoneNumber or "")

            description = place.description or ""

            if domain and name:
                self._save_lead(
                    domain, name, place.website or "", phone, description, "maps"
                )

    # --- PIPELINE 2: SEARCH (shallow collection) ---
    def run_search_pipeline(self, query: str) -> None:
        """Run the Search pipeline: fetch organic results and save as leads."""
        logger.info(f"Starting Search pipeline: {query}")
        response = self.client.search(query)
        organic_results = response.organic[: settings.SERPER_MAX_RESULTS]

        for item in organic_results:
            domain = self._extract_domain(item.link)

            if self._is_blacklisted(domain):
                logger.debug(f"[TRACE] Search skipped blacklisted domain: {domain}")
                continue

            raw_title = item.title.split("-")[0].split("|")[0].strip()[:49]
            name = clean_company_name(raw_title) or domain.split(".")[0].capitalize()
            phone = self._extract_phone_from_text(item.snippet)
            description = item.snippet or ""

            if domain and name:
                self._save_lead(domain, name, item.link, phone, description, "search")

    # --- PIPELINES 3 & 4: DEEP SCRAPE (threaded) ---
    def run_deep_scrape(
        self,
        targets: list[dict[str, str]],
        source_method: str = "hybrid",
        max_workers: int = settings.SCRAPER_MAX_WORKERS,
    ) -> None:
        """Scrape a list of target URLs in parallel and save results as leads."""
        logger.info(
            f"Starting Deep Scrape ({source_method}) for {len(targets)} targets"
        )

        def scrape_worker(target: dict[str, str]):
            url = target.get("url", "")
            domain = self._extract_domain(url)

            logger.debug(f"[TRACE] Starting processing: {domain}")

            if not domain:
                logger.debug(f"[TRACE] Thread exit (empty domain): {url}")
                return

            if self._is_blacklisted(domain):
                logger.debug(f"[TRACE] Thread exit (blacklisted domain): {domain}")
                return

            if domain in self.visited_domains:
                logger.debug(f"[TRACE] Thread exit (session duplicate): {domain}")
                return

            self.visited_domains.add(domain)

            raw_title = (
                (target.get("name") or "").split("-")[0].split("|")[0].strip()[:49]
            )
            name = clean_company_name(raw_title) or domain.split(".")[0].capitalize()

            if not name:
                logger.debug(
                    f"[TRACE] Thread exit (cannot generate name): {domain} from raw '{raw_title}'"
                )
                return

            logger.debug(f"[TRACE] Starting HTTP scrape: {domain}")
            scrape_resp = self.client.scrape(url)
            text_content = scrape_resp.markdown or scrape_resp.text

            if not text_content:
                logger.warning(
                    f"[TRACE] Serper returned empty text (possible 500/403): {domain}"
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
                f"[TRACE] Saving to DB: {domain} | Phone: '{phone}' | Desc: '{description[:10]}...'"
            )
            self._save_lead(domain, name, url, phone, description, source_method)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(scrape_worker, t) for t in targets]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Scrape thread error: {e}")
