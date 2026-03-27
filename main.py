import argparse
from app.database import engine, Base, SessionLocal
from app.models import LEEDData
from app.scraper.client import RequestClient
from app.scraper.parser import LEEDParser
from app.sender.worker import WebhookWorker
from app.utils.logger import logger


def init_db():
    """Ініціалізувати базу даних"""
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized")


def scrape_command(url: str):
    """
    Команда для скрейпінгу

    Args:
        url: URL для скрейпінгу
    """
    logger.info(f"Starting scrape for {url}")

    client = RequestClient()
    parser = LEEDParser()
    db = SessionLocal()

    try:
        response = client.get(url)
        if not response:
            logger.error(f"Failed to fetch {url}")
            return

        data = parser.parse_html(response.text)
        if not data:
            logger.error(f"Failed to parse {url}")
            return

        # Зберегти в БД
        leed_data = LEEDData(
            title=data.get("title", ""),
            description=data.get("description"),
            url=url,
            status="completed"
        )
        db.add(leed_data)
        db.commit()

        logger.info(f"Successfully scraped {url}")

    finally:
        client.close()
        db.close()


def send_command():
    """Команда для відправки даних на Webhook"""
    logger.info("Starting webhook sender")

    db = SessionLocal()
    worker = WebhookWorker()

    try:
        worker.process_pending(db)
    finally:
        db.close()


def main():
    """Основна функція для CLI"""
    parser = argparse.ArgumentParser(description="MAKE LEED GEN - Scraper та Sender")
    subparsers = parser.add_subparsers(dest="command", help="Команди")

    # scrape команда
    scrape_parser = subparsers.add_parser("scrape", help="Скрейпити дані")
    scrape_parser.add_argument("--url", required=True, help="URL для скрейпінгу")

    # send команда
    subparsers.add_parser("send", help="Відправити дані на Webhook")

    # init команда
    subparsers.add_parser("init", help="Ініціалізувати базу даних")

    args = parser.parse_args()

    if args.command == "init":
        init_db()
    elif args.command == "scrape":
        scrape_command(args.url)
    elif args.command == "send":
        send_command()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
