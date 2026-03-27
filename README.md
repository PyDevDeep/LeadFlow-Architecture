# MAKE LEED GEN

Додаток для скрейпінгу та обробки LEED даних з подальшою відправкою на Webhook.

## Встановлення

1. Клонуй репозиторій
2. Встанови залежності:
   ```bash
   pip install -r requirements.txt
   ```

3. Скопіюй `.env.example` в `.env` та налаштуй:
   ```bash
   cp .env.example .env
   ```

4. Ініціалізуй базу даних:
   ```bash
   python main.py init
   ```

## Використання

### Скрейпити дані
```bash
python main.py scrape --url https://example.com
```

### Відправити дані на Webhook
```bash
python main.py send
```

## Архітектура

Див. [architecture.md](architecture.md)

## Конфігурація

Усі параметри у `.env`:
- `DATABASE_URL` - Підключення до БД
- `WEBHOOK_URL` - URL для відправки
- `SCRAPER_TIMEOUT` - Timeout для HTTP запитів
- `WEBHOOK_BATCH_SIZE` - Розмір батчу для відправки

## Структура проекту

```
./
    README.md
    architecture.md
    main.py
    requirements.txt
    app/
        __init__.py
        config.py
        database.py
        models.py
        scraper/
            __init__.py
            client.py
            parser.py
        sender/
            __init__.py
            worker.py
        utils/
            logger.py
```

## Розробка

Запуск тестів:
```bash
pytest
```

Форматування коду:
```bash
black .
isort .
```
