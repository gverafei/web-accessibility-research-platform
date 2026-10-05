import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

if "database" not in sys.modules:
    database_stub = types.ModuleType("database")
    database_stub.init_db = lambda: None
    database_stub.get_connection = lambda: None
    sys.modules["database"] = database_stub

main = importlib.import_module("main")
experiments_module = importlib.import_module("routes.experiments")


class FakeCursor:
    def __init__(self):
        self.lastrowid = 42
        self.executions = []

    def execute(self, statement, parameters=None):
        self.executions.append((statement, parameters))

    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def commit(self):
        pass

    def close(self):
        pass


class LlmSelectionTestCase(unittest.TestCase):
    def setUp(self):
        self.client = main.app.test_client()
        main.app.config.update(
            OPENROUTER_API_KEY_CONFIGURED=True,
            OPENROUTER_BASE_URL_CONFIGURED=True,
            WAVE_API_KEY_CONFIGURED=True,
            LLAMA_MODEL="meta-llama/test",
            CLAUDE_MODEL="anthropic/test",
        )

    def test_acquisition_form_does_not_offer_llm_review(self):
        response = self.client.get("/acquisition/new")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'name="include_semantic"', response.data)
        self.assertNotIn(b'name="semantic_provider"', response.data)
        self.assertIn(b'name="include_wave"', response.data)
        self.assertNotIn(b'id="processingBox"', response.data)
        self.assertIn(b"js/ui_feedback.js", response.data)
        self.assertNotIn(b"submitButton.disabled = true", response.data)
        self.assertIn(b'id="urlCount"', response.data)
        self.assertNotIn(b"maxManualUrls", response.data)

    def test_manual_acquisition_accepts_more_than_one_hundred_urls(self):
        connection = FakeConnection()
        urls = "\n".join(f"https://example.com/page-{index}" for index in range(101))

        with patch.object(experiments_module, "get_connection", return_value=connection):
            response = self.client.post("/run", data={"source_type": "url", "urls": urls})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/experiments/42"))
        statement, parameters = connection.cursor_instance.executions[-1]
        self.assertIn("INSERT INTO experiments", statement)
        self.assertEqual(len(parameters[1].splitlines()), 101)

    def test_manual_acquisition_accepts_one_hundred_urls(self):
        connection = FakeConnection()
        urls = "\n".join(f"https://example.com/page-{index}" for index in range(100))

        with patch.object(experiments_module, "get_connection", return_value=connection):
            response = self.client.post(
                "/run",
                data={"source_type": "url", "title": "Manual pilot", "urls": urls},
            )

        self.assertEqual(response.status_code, 302)
        statement, parameters = connection.cursor_instance.executions[-1]
        self.assertIn("INSERT INTO experiments", statement)
        self.assertEqual(len(parameters[1].splitlines()), 100)

    def test_unconfigured_optional_services_are_not_offered(self):
        with patch.dict(main.app.config, {
            "OPENROUTER_API_KEY_CONFIGURED": False,
            "OPENROUTER_BASE_URL_CONFIGURED": False,
            "WAVE_API_KEY_CONFIGURED": False,
        }):
            response = self.client.get("/acquisition/new")

        self.assertNotIn(b'name="include_semantic"', response.data)
        self.assertNotIn(b'name="semantic_provider"', response.data)
        self.assertNotIn(b'name="include_wave"', response.data)

    def test_unconfigured_service_cannot_be_requested_directly(self):
        with patch.dict(main.app.config, {"WAVE_API_KEY_CONFIGURED": False}):
            response = self.client.post("/run", data={
                "title": "Invalid WAVE experiment",
                "urls": "https://example.com",
                "include_wave": "on",
            })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/acquisition/new"))

    def test_llm_fields_submitted_directly_are_ignored_for_acquisition(self):
        connection = FakeConnection()

        with patch.object(experiments_module, "get_connection", return_value=connection):
            response = self.client.post(
                "/run",
                data={
                    "title": "Gemini experiment",
                    "urls": "https://example.com",
                    "include_semantic": "on",
                    "include_wave": "on",
                    "semantic_provider": "gemini",
                },
            )

        self.assertEqual(response.status_code, 302)
        statement, parameters = connection.cursor_instance.executions[-1]
        self.assertIn("'queued'", statement)
        self.assertTrue(parameters[3])
        self.assertFalse(parameters[2])
        self.assertIsNone(parameters[4])
        self.assertIsNone(parameters[5])


if __name__ == "__main__":
    unittest.main()
