import sqlite3
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import HTTPError, RequestException

from app.database import get_db_connection, init_db
from app.schemas.serper import (
    SerperMapsResponse,
    SerperScrapeResponse,
    SerperSearchResponse,
)
from app.scraper.manager import ScrapeManager
from app.scraper.serper_client import SerperClient
from app.sender.worker import handle_retry, process_batch
from app.utils.validators import clean_company_name, clean_phone

# ==========================================
# 1. ТЕСТИ УТИЛІТ (app.utils.validators)
# ==========================================


class TestValidators:
    """Тестування чистих функцій. Ризик: некоректна нормалізація даних перед записом в БД."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("+380441112233", "+380441112233"),
            ("380441112233", "+380441112233"),
            ("0501234567", "+380501234567"),
            ("12125550198", "+12125550198"),
            ("2125550198", "+12125550198"),
            ("invalid", ""),
            ("", ""),
        ],
    )
    def test_clean_phone(self, raw: str, expected: str) -> None:
        assert clean_phone(raw) == expected

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("Google LLC", "Google"),
            ("Gamma Solutions Inc.", "Gamma Solutions"),
            ("Delta Tech ltd", "Delta Tech"),
            ("a", None),
            ("home", None),
            ("", None),
            ("   Extra   Spaces   ", "Extra Spaces"),
        ],
    )
    def test_clean_company_name(self, raw: str, expected: str | None) -> None:
        assert clean_company_name(raw) == expected


# ==========================================
# 2. ТЕСТИ МЕНЕДЖЕРА (app.scraper.manager)
# ==========================================


class ExposedScrapeManager(ScrapeManager):
    """
    Допоміжний клас-нащадок для легального доступу до захищених методів
    в умовах суворого статичного аналізу Pylance.
    """

    def public_extract_domain(self, url: str) -> str:
        return self._extract_domain(url)

    def public_is_blacklisted(self, domain: str) -> bool:
        return self._is_blacklisted(domain)

    def public_save_lead(
        self,
        domain: str,
        name: str,
        website: str,
        phone: str,
        description: str,
        source_method: str,
    ) -> None:
        self._save_lead(domain, name, website, phone, description, source_method)

    def public_extract_phone_from_text(self, text: str | None) -> str:
        return self._extract_phone_from_text(text)


class TestScrapeManager:
    """Тестування бізнес-логіки. Ризик: пропуск валідних лідів або збереження сміття."""

    @pytest.fixture
    def manager(self) -> ExposedScrapeManager:
        # Використовуємо наш підклас замість оригінального менеджера
        return ExposedScrapeManager()

    def test_extract_domain(self, manager: ExposedScrapeManager) -> None:
        # Тепер ми викликаємо публічні методи-обгортки
        assert (
            manager.public_extract_domain("https://www.google.com/path") == "google.com"
        )
        assert manager.public_extract_domain("example.net") == "example.net"
        assert manager.public_extract_domain("") == ""

    def test_is_blacklisted(self, manager: ExposedScrapeManager) -> None:
        assert manager.public_is_blacklisted("medium.com/article") is True
        assert manager.public_is_blacklisted("legit-company.com") is False

    @patch("app.scraper.manager.get_db_connection")
    def test_save_lead_valid(
        self, mock_db: MagicMock, manager: ExposedScrapeManager
    ) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1  # Покриття рядків 75-76: новий лід (rowcount > 0)
        mock_conn.execute.return_value = mock_cursor
        mock_db.return_value.__enter__.return_value = mock_conn

        manager.public_save_lead(
            "test.com", "Test", "http://test.com", "+380501234567", "", "maps"
        )

        mock_conn.execute.assert_called_once()
        args = mock_conn.execute.call_args[0][1]
        assert args[0] == "test.com"
        assert args[3] == "+380501234567"

    @patch("app.scraper.manager.get_db_connection")
    def test_save_lead_duplicate_ignored(
        self, mock_db: MagicMock, manager: ExposedScrapeManager
    ) -> None:
        """Покриття рядків 77-78: INSERT OR IGNORE не вставив (дублікат домену)."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0  # Дублікат — БД проігнорувала INSERT
        mock_conn.execute.return_value = mock_cursor
        mock_db.return_value.__enter__.return_value = mock_conn

        manager.public_save_lead(
            "test.com", "Test", "http://test.com", "+380501234567", "", "maps"
        )

    @patch("app.scraper.manager.get_db_connection")
    def test_save_lead_empty_contact(
        self, mock_db: MagicMock, manager: ExposedScrapeManager
    ) -> None:
        manager.public_save_lead("test.com", "Test", "http://test.com", "", "", "maps")
        mock_db.assert_not_called()

    @patch("app.scraper.manager.ScrapeManager._save_lead")
    @patch("app.scraper.manager.SerperClient.maps")
    def test_run_maps_pipeline(
        self,
        mock_maps: MagicMock,
        mock_save_lead: MagicMock,
        manager: ExposedScrapeManager,
    ) -> None:
        mock_maps_resp = MagicMock()
        # Імітуємо один валідний і один сміттєвий домен (з чорного списку)
        place1 = MagicMock(
            website="http://good.com", title="Good", phoneNumber="123", description=""
        )
        place2 = MagicMock(
            website="http://medium.com", title="Bad", phoneNumber="456", description=""
        )
        mock_maps_resp.places = [place1, place2]
        mock_maps.return_value = mock_maps_resp

        manager.run_maps_pipeline("query")

        # Збереження має викликатись тільки для good.com
        mock_save_lead.assert_called_once()
        assert mock_save_lead.call_args[0][0] == "good.com"

    @patch("app.scraper.manager.ScrapeManager._save_lead")
    @patch("app.scraper.manager.SerperClient.search")
    def test_run_search_pipeline(
        self,
        mock_search: MagicMock,
        mock_save_lead: MagicMock,
        manager: ExposedScrapeManager,
    ) -> None:
        mock_search_resp = MagicMock()
        org1 = MagicMock(
            link="http://good.com", title="Good", snippet="Call +380501234567"
        )
        mock_search_resp.organic = [org1]
        mock_search.return_value = mock_search_resp

        manager.run_search_pipeline("query")

        mock_save_lead.assert_called_once()
        assert mock_save_lead.call_args[0][0] == "good.com"
        assert mock_save_lead.call_args[0][3] == "+380501234567"

    @patch("app.scraper.manager.settings")
    def test_manager_regex_compile_error(self, mock_settings: MagicMock) -> None:
        # Штучно ламаємо регулярний вираз для перевірки критичної зупинки
        mock_settings.ACTIVE_PHONE_REGEX = "*[invalid"
        with pytest.raises(SystemExit):
            ScrapeManager()

    def test_is_blacklisted_empty(self, manager: ExposedScrapeManager) -> None:
        # Порожній домен має вважатися чорним списком згідно з контекстом
        assert manager.public_is_blacklisted("") is True

    def test_extract_phone_empty(self, manager: ExposedScrapeManager) -> None:
        assert manager.public_extract_phone_from_text(None) == ""

    def test_save_lead_empty_name(self, manager: ExposedScrapeManager) -> None:
        # Без домену або імені запис не повинен відбуватися
        manager.public_save_lead("", "", "url", "1", "D", "maps")

    @patch("app.scraper.manager.get_db_connection")
    def test_save_lead_db_exception(
        self, mock_db: MagicMock, manager: ExposedScrapeManager
    ) -> None:
        # Імітуємо падіння БД під час збереження
        mock_db.return_value.__enter__.side_effect = Exception("DB Error")
        manager.public_save_lead("test.com", "Name", "url", "1", "D", "maps")
        # Тест пройде, якщо виключення коректно перехоплено і не "поклало" програму

    @patch("app.scraper.manager.ScrapeManager._save_lead")
    @patch("app.scraper.manager.SerperClient.search")
    def test_run_search_pipeline_blacklist(
        self,
        mock_search: MagicMock,
        mock_save: MagicMock,
        manager: ExposedScrapeManager,
    ) -> None:
        mock_search_resp = MagicMock()
        org1 = MagicMock(link="http://medium.com", title="Bad", snippet="")
        mock_search_resp.organic = [org1]
        mock_search.return_value = mock_search_resp

        manager.run_search_pipeline("query")
        mock_save.assert_not_called()  # Домен з чорного списку пропущено

    @patch("app.scraper.manager.SerperClient.scrape")
    @patch("app.scraper.manager.ScrapeManager._save_lead")
    def test_run_deep_scrape(
        self,
        mock_save: MagicMock,
        mock_scrape: MagicMock,
        manager: ExposedScrapeManager,
    ) -> None:
        # Перевірка мультипоточного скрейпера
        targets = [
            {"url": "http://good.com", "name": "Good"},
            {"url": "http://medium.com"},
        ]
        mock_scrape_resp = MagicMock()
        mock_scrape_resp.text = "Contact: +380501234567"
        mock_scrape_resp.markdown = None
        mock_scrape_resp.metadata = {"Description": "Test Desc"}
        mock_scrape.return_value = mock_scrape_resp

        manager.run_deep_scrape(targets, source_method="hybrid", max_workers=1)

        # Перевіряємо, що збереження викликано тільки для валідного домену
        mock_save.assert_called_once()

    @patch("app.scraper.manager.get_db_connection")
    def test_save_lead_execute_exception(
        self, mock_db: MagicMock, manager: ExposedScrapeManager
    ) -> None:
        # Покриття рядків 75-77: Помилка збереження
        # Найпростіший спосіб викликати виключення в блоці try - зламати сам виклик get_db_connection
        mock_db.side_effect = Exception("DB Connect Error")

        manager.public_save_lead(
            "test.com", "Test", "http://test.com", "123", "", "maps"
        )

        # Якщо тест не впав з помилкою Exception("DB Connect Error"),
        # значить блок except Exception as e успішно її перехопив.
        assert mock_db.called

    @patch("app.scraper.manager.SerperClient.scrape")
    @patch("app.scraper.manager.ScrapeManager._save_lead")
    def test_run_deep_scrape_edge_cases(
        self,
        mock_save: MagicMock,
        mock_scrape: MagicMock,
        manager: ExposedScrapeManager,
    ) -> None:
        # Покриття рядків 145-183: Усі варіанти "смерті" потоку
        targets: list[dict[str, str]] = [
            {
                "url": "",
                "name": "A",
            },  # 145-146: Пустий URL → пустий домен → потік гине
            {"url": "http://dup.com", "name": "B"},  # Валідний запис
            {"url": "http://dup.com", "name": "C"},  # 156-159: Дублікат сесії
            {
                "url": "http://.xyz",
                "name": "home",
            },  # 170-173: Пусте ім'я (home відкидається, .xyz стає пустим)
            {
                "url": "http://notext.com",
                "name": "E",
            },  # 180-183: API повернуло пустий текст
        ]

        mock_scrape_empty = MagicMock(text=None, markdown=None, metadata=None)
        mock_scrape_valid = MagicMock(
            text="Phone: +380501234567", markdown=None, metadata={}
        )

        def scrape_side_effect(url: str) -> MagicMock:
            if "notext" in url:
                return mock_scrape_empty
            return mock_scrape_valid

        mock_scrape.side_effect = scrape_side_effect

        manager.run_deep_scrape(targets, source_method="hybrid", max_workers=1)

        # До БД має дійти рівно ОДИН запис ("http://dup.com", "B")
        assert mock_save.call_count == 1

    @patch("app.scraper.manager.SerperClient.scrape")
    def test_run_deep_scrape_worker_exception(
        self, mock_scrape: MagicMock, manager: ExposedScrapeManager
    ) -> None:
        # Покриття рядків 204-205: Перехоплення виключень усередині ThreadPoolExecutor
        mock_scrape.side_effect = Exception("Worker Crash")
        targets = [{"url": "http://crash.com", "name": "Crash"}]

        manager.run_deep_scrape(targets, source_method="hybrid", max_workers=1)
        # Має просто залогувати помилку, а не "покласти" весь додаток


# ==========================================
# 3. ТЕСТИ КЛІЄНТА API (app.scraper.serper_client)
# ==========================================


class TestSerperClient:
    """Тестування HTTP клієнта. Ризик: падіння при нестандартних відповідях API."""

    @patch("app.scraper.serper_client.requests.post")
    def test_maps_success(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "places": [{"title": "Test Place", "phoneNumber": "123"}]
        }
        mock_post.return_value = mock_response

        client = SerperClient()
        result = client.maps("test query")

        assert isinstance(result, SerperMapsResponse)
        assert len(result.places) == 1
        assert result.places[0].title == "Test Place"

    @patch("app.scraper.serper_client.requests.post")
    def test_maps_http_error(self, mock_post: MagicMock) -> None:
        mock_post.return_value.raise_for_status.side_effect = HTTPError("403 Forbidden")

        client = SerperClient()
        result = client.maps("test query")

        assert isinstance(result, SerperMapsResponse)
        assert len(result.places) == 0

    @patch("app.scraper.serper_client.requests.post")
    def test_search_success(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "organic": [{"title": "T", "link": "http://link.com", "snippet": "S"}]
        }
        mock_post.return_value = mock_response

        client = SerperClient()
        result = client.search("test")

        assert isinstance(result, SerperSearchResponse)
        assert len(result.organic) == 1

    @patch("app.scraper.serper_client.requests.post")
    def test_scrape_success(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"text": "Content", "metadata": {}}
        mock_post.return_value = mock_response

        client = SerperClient()
        result = client.scrape("http://test.com")

        assert isinstance(result, SerperScrapeResponse)
        assert result.text == "Content"

    @patch("app.scraper.serper_client.settings")
    def test_no_api_key(self, mock_settings: MagicMock) -> None:
        # Семантично перевіряємо обробку відсутнього ключа
        mock_settings.SERPER_API_KEY = ""
        client = SerperClient()
        assert client.headers.get("X-API-KEY") == ""

    @patch("app.scraper.serper_client.requests.post")
    def test_search_http_error(self, mock_post: MagicMock) -> None:
        mock_post.return_value.raise_for_status.side_effect = HTTPError("Search Error")
        client = SerperClient()
        result = client.search("query")
        assert len(result.organic) == 0

    @patch("app.scraper.serper_client.requests.post")
    def test_scrape_http_error(self, mock_post: MagicMock) -> None:
        mock_post.return_value.raise_for_status.side_effect = HTTPError("Scrape Error")
        client = SerperClient()
        result = client.scrape("http://test.com")
        assert result.text is None


# ==========================================
# 4. ТЕСТИ ВОРКЕРА (app.sender.worker)
# ==========================================


class TestSenderWorker:
    """Тестування відправки webhook. Ризик: втрата даних при таймаутах сервера."""

    @patch("app.sender.worker.get_leads_for_processing")
    @patch("app.sender.worker.requests.post")
    @patch("app.sender.worker.update_lead_status")
    def test_process_batch_success(
        self, mock_update: MagicMock, mock_post: MagicMock, mock_get_leads: MagicMock
    ) -> None:
        mock_get_leads.return_value = [
            {
                "id": 1,
                "domain": "a.com",
                "name": "A",
                "website": "",
                "phone": "1",
                "description": "D",
                "source_method": "S",
                "retry_count": 0,
            }
        ]

        process_batch()

        mock_post.assert_called_once()
        mock_update.assert_called_once_with(1, "success")

    @patch("app.sender.worker.get_leads_for_processing")
    @patch("app.sender.worker.requests.post")
    @patch("app.sender.worker.handle_retry")
    def test_process_batch_rate_limit(
        self,
        mock_handle_retry: MagicMock,
        mock_post: MagicMock,
        mock_get_leads: MagicMock,
    ) -> None:
        # Явна типізація для уникнення reportUnknownVariableType
        leads: list[dict[str, Any]] = [
            {
                "id": 1,
                "domain": "a.com",
                "name": "A",
                "website": "",
                "phone": "1",
                "description": "D",
                "source_method": "S",
                "retry_count": 0,
            }
        ]
        mock_get_leads.return_value = leads

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_post.return_value.raise_for_status.side_effect = HTTPError(
            response=mock_response
        )

        process_batch()

        mock_handle_retry.assert_called_once_with(leads)

    @patch("app.sender.worker.update_lead_status")
    @patch("app.sender.worker.time.time", return_value=1000)
    def test_handle_retry_logic(
        self, mock_time: MagicMock, mock_update: MagicMock
    ) -> None:
        # Явна типізація словників
        leads_continue: list[dict[str, Any]] = [{"id": 1, "retry_count": 0}]
        leads_fail: list[dict[str, Any]] = [{"id": 2, "retry_count": 4}]

        handle_retry(leads_continue)
        handle_retry(leads_fail)

        calls = mock_update.call_args_list
        assert calls[0][0][1] == "pending"
        assert calls[1][0][1] == "failed"

    @patch("app.sender.worker.get_leads_for_processing")
    def test_process_batch_empty(self, mock_get: MagicMock) -> None:
        mock_get.return_value = []
        process_batch()  # Тест покриває вихід, коли черга порожня

    @patch("app.sender.worker.get_leads_for_processing")
    @patch("app.sender.worker.requests.post")
    @patch("app.sender.worker.handle_retry")
    def test_process_batch_request_exception(
        self, mock_retry: MagicMock, mock_post: MagicMock, mock_get: MagicMock
    ) -> None:
        leads: list[dict[str, Any]] = [
            {
                "id": 1,
                "domain": "a.com",
                "name": "A",
                "website": "",
                "phone": "1",
                "description": "D",
                "source_method": "S",
                "retry_count": 0,
            }
        ]
        mock_get.return_value = leads
        mock_post.side_effect = RequestException("Network Timeout")

        process_batch()
        mock_retry.assert_called_once_with(leads)

    @patch("app.sender.worker.get_leads_for_processing")
    @patch("app.sender.worker.requests.post")
    def test_process_batch_general_exception(
        self, mock_post: MagicMock, mock_get: MagicMock
    ) -> None:
        leads: list[dict[str, Any]] = [
            {
                "id": 1,
                "domain": "a",
                "name": "A",
                "website": "",
                "phone": "1",
                "description": "D",
                "source_method": "S",
                "retry_count": 0,
            }
        ]
        mock_get.return_value = leads
        mock_post.side_effect = Exception("Critical Error")
        process_batch()  # Має перехопити і залогувати

    @patch("app.sender.worker.get_db_connection")
    def test_update_lead_status(self, mock_db: MagicMock) -> None:
        from app.sender.worker import update_lead_status

        mock_conn = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_conn

        update_lead_status(1, "success", 1, 123)
        mock_conn.execute.assert_called_once()

    @patch("app.sender.worker.get_db_connection")
    def test_get_leads_for_processing(self, mock_db: MagicMock) -> None:
        from app.sender.worker import get_leads_for_processing

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [{"id": 1}]
        mock_db.return_value.__enter__.return_value = mock_conn

        result = get_leads_for_processing(10)
        assert result == [{"id": 1}]

    @patch("app.sender.worker.get_leads_for_processing")
    @patch("app.sender.worker.requests.post")
    @patch("app.sender.worker.update_lead_status")
    def test_process_batch_http_400(
        self, mock_update: MagicMock, mock_post: MagicMock, mock_get: MagicMock
    ) -> None:
        # Покриття рядків 62-63: HTTP помилки, які не входять у список "тимчасових" (напр. 400 Bad Request)
        leads: list[dict[str, Any]] = [
            {
                "id": 1,
                "domain": "a.com",
                "name": "A",
                "website": "",
                "phone": "1",
                "description": "D",
                "source_method": "S",
                "retry_count": 0,
            }
        ]
        mock_get.return_value = leads

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_post.return_value.raise_for_status.side_effect = HTTPError(
            response=mock_response
        )

        process_batch()
        # Статус має змінитись на failed без передачі у функцію handle_retry
        mock_update.assert_called_once_with(1, "failed")

    @patch("app.sender.worker.get_db_connection")
    def test_worker_db_exceptions(self, mock_db: MagicMock) -> None:
        # Покриття рядків 117-118 та 142-144: Падіння БД під час читання/запису
        import sqlite3

        from app.sender.worker import get_leads_for_processing, update_lead_status

        mock_db.return_value.__enter__.side_effect = sqlite3.Error("DB Error")

        # Перевірка 117-118
        update_lead_status(1, "success")  # Має коректно перехопити

        # Перевірка 142-144
        result = get_leads_for_processing(10)
        assert result == []  # При помилці читання повертаємо пустий список

    def test_worker_main_block(self) -> None:
        # Покриття рядка 148: if __name__ == "__main__":
        import runpy

        # Ми дозволяємо модулю реально запуститися через runpy,
        # але мокаємо get_leads_for_processing так, щоб черга була порожньою.
        # Таким чином код просто залогує "Черга порожня" і безпечно завершиться.
        with patch("app.sender.worker.get_leads_for_processing", return_value=[]):
            runpy.run_module("app.sender.worker", run_name="__main__")
            # Відсутність виключень означає, що блок виконався успішно


# ==========================================
# 5. ТЕСТИ БАЗИ ДАНИХ (app.database)
# ==========================================


class TestDatabase:
    """Тестування взаємодії зі SQLite. Ризик: витоки з'єднань або помилки ініціалізації."""

    @patch("app.database.sqlite3.connect")
    def test_get_db_connection(self, mock_connect: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        with get_db_connection() as conn:
            assert conn == mock_conn

        # Перевіряємо, що з'єднання гарантовано закривається (блок finally)
        mock_conn.close.assert_called_once()

    @patch("app.database.get_db_connection")
    def test_init_db_success(self, mock_get_db: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_conn

        init_db()

        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch("app.database.get_db_connection")
    def test_init_db_error(self, mock_get_db: MagicMock) -> None:
        # Перевірка обробки помилок (sqlite3.Error)
        mock_get_db.return_value.__enter__.side_effect = sqlite3.Error("Test DB Error")
        init_db()  # Не повинно викликати виключення, бо помилка логується
