import argparse
import os

from app.config import settings
from app.database import init_db
from app.scraper.manager import ScrapeManager
from app.sender.worker import process_batch
from app.utils.logger import logger


def main():
    parser = argparse.ArgumentParser(description="MAKE LEAD GEN - CLI")
    subparsers = parser.add_subparsers(dest="command", help="Команди", required=True)

    # Команда: init
    subparsers.add_parser("init", help="Ініціалізувати базу даних")

    # Команда: send
    subparsers.add_parser("send", help="Відправити дані на Webhook")

    # Команда: maps
    maps_parser = subparsers.add_parser("maps", help="Сценарій 1: Google Maps")
    maps_parser.add_argument("-q", "--query", required=True, help="Пошуковий запит")

    # Команда: search
    search_parser = subparsers.add_parser("search", help="Сценарій 2: Google Search")
    search_parser.add_argument("-q", "--query", required=True, help="Пошуковий запит")

    # Команда: hybrid (Search + Deep Scrape)
    hybrid_parser = subparsers.add_parser(
        "hybrid", help="Сценарій 3: Search -> Deep Scrape"
    )
    hybrid_parser.add_argument("-q", "--query", required=True, help="Пошуковий запит")

    # Команда: file (TXT -> Deep Scrape)
    file_parser = subparsers.add_parser(
        "file", help="Сценарій 4: TXT File -> Deep Scrape"
    )
    file_parser.add_argument(
        "-f", "--filepath", required=True, help="Шлях до txt файлу з посиланнями"
    )

    args = parser.parse_args()
    logger.info(f"Запуск CLI з командою: {args.command}")

    if args.command == "init":
        init_db()

    elif args.command == "send":
        process_batch()

    elif args.command in ["maps", "search", "hybrid", "file"]:
        manager = ScrapeManager()

        if args.command == "maps":
            manager.run_maps_pipeline(args.query)

        elif args.command == "search":
            manager.run_search_pipeline(args.query)

        elif args.command == "hybrid":
            # Спочатку отримуємо органіку, потім парсимо глибоко
            search_resp = manager.client.search(args.query)

            # ОБРІЗАЄМО МАСИВ ПЕРЕД DEEP SCRAPE
            organic_results = search_resp.organic[: settings.SERPER_MAX_RESULTS]
            targets = [
                {"url": item.link, "name": item.title} for item in organic_results
            ]

            manager.run_deep_scrape(targets)

        elif args.command == "file":
            if not os.path.exists(args.filepath):
                logger.error(f"Файл {args.filepath} не знайдено.")
                return

            with open(args.filepath, "r", encoding="utf-8") as f:
                urls = [line.strip() for line in f if line.strip()]

            urls = urls[: settings.SERPER_MAX_RESULTS]
            targets = [{"url": url} for url in urls]
            # Явно вказуємо, що джерело - file
            manager.run_deep_scrape(
                targets, source_method="file", max_workers=settings.SCRAPER_MAX_WORKERS
            )


if __name__ == "__main__":
    main()
