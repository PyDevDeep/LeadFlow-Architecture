import argparse

from app.database import init_db
from app.scraper.scraper import run_scraper
from app.sender.worker import process_batch
from app.utils.logger import logger


def main():
    parser = argparse.ArgumentParser(description="MAKE LEAD GEN - CLI")
    subparsers = parser.add_subparsers(dest="command", help="Команди", required=True)

    scrape_parser = subparsers.add_parser("scrape", help="Скрейпити дані")
    scrape_parser.add_argument("--url", required=True, help="URL для скрейпінгу")

    subparsers.add_parser("send", help="Відправити дані на Webhook")
    subparsers.add_parser("init", help="Ініціалізувати базу даних")

    args = parser.parse_args()

    # Використовуємо логер для фіксації запуску
    logger.info(f"Запуск CLI з командою: {args.command}")

    if args.command == "init":
        init_db()
    elif args.command == "scrape":
        run_scraper(args.url)
    elif args.command == "send":
        process_batch()


if __name__ == "__main__":
    main()
