import argparse


def main():
    """Основна функція для CLI"""
    parser = argparse.ArgumentParser(description="MAKE LEAD GEN - Scraper та Sender")
    subparsers = parser.add_subparsers(dest="command", help="Команди")

    # scrape команда
    scrape_parser = subparsers.add_parser("scrape", help="Скрейпити дані")
    scrape_parser.add_argument("--url", required=True, help="URL для скрейпінгу")

    # send команда
    subparsers.add_parser("send", help="Відправити дані на Webhook")

    # init команда
    subparsers.add_parser("init", help="Ініціалізувати базу даних")

    parser.print_help()


if __name__ == "__main__":
    main()
