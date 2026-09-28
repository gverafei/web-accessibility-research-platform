"""Large submissions are tested offline: no live queues or browser acquisitions."""

import importlib
import importlib.util
import io
import json
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup
from flask import render_template
from werkzeug.datastructures import FileStorage


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))
if "database" not in sys.modules:
    stub = types.ModuleType("database")
    stub.init_db = lambda: None
    stub.get_connection = lambda: None
    sys.modules["database"] = stub

main = importlib.import_module("main")
routes = importlib.import_module("routes.experiments")
from dataset_storage import import_dataset
from settings import SETTING_DEFAULTS
from tranco_sampling import TRANCO_STRATA, sample_tranco


class AcquisitionCapacityTests(unittest.TestCase):
    def setUp(self):
        self.cursor = Mock(lastrowid=73)
        self.connection = Mock()
        self.connection.cursor.return_value = self.cursor
        self.settings_patch = patch.object(routes, "get_settings", return_value=dict(SETTING_DEFAULTS))
        self.connection_patch = patch.object(routes, "get_connection", return_value=self.connection)
        self.settings_patch.start()
        self.connection_patch.start()
        self.addCleanup(self.settings_patch.stop)
        self.addCleanup(self.connection_patch.stop)
        self.client = main.app.test_client()

    def queued_urls(self):
        calls = [call.args for call in self.cursor.execute.call_args_list
                 if "INSERT INTO experiments (" in call.args[0]]
        self.assertEqual(len(calls), 1)
        return calls[0][1][1]

    def test_million_url_submission_is_queued_without_a_count_cap(self):
        # Memory-only SQL mock: this never writes to the operational database.
        text = "\n".join(f"https://site-{i}.example/" for i in range(1_000_000))
        response = self.client.post("/run", data={"source_type": "url", "title": "Large offline test",
                                                  "urls": text})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/experiments/73")
        self.assertEqual(self.queued_urls(), text)
        self.connection.commit.assert_called_once()

    def test_tranco_large_allocation_is_queued_with_actual_reserve_counts(self):
        sizes = [200, 250, 300, 450, 600]
        ranking = []
        data = {"source_type": "tranco", "title": "Independent allocation", "tranco_seed": "test-seed"}
        for (label, _name, lower, _upper), count in zip(TRANCO_STRATA, sizes):
            data[f"tranco_count_{label}"] = str(count)
            ranking.extend((rank, f"site-{rank}.example") for rank in range(lower, lower + count))
        metadata = {"list_sha256": "a" * 64, "source_filename": "synthetic.csv", "frame_size": len(ranking)}
        with patch.object(routes, "fetch_latest_standard_list", return_value=(b"mock", "synthetic.csv", "TEST123")), \
                patch.object(routes, "parse_tranco", return_value=(ranking, metadata)):
            response = self.client.post("/run", data=data)
        self.assertEqual(response.headers["Location"], "/experiments/73")
        self.assertEqual(len(self.queued_urls().splitlines()), 1800)
        sample = next(call.args[1] for call in self.cursor.execute.call_args_list
                      if "INSERT INTO tranco_samples (" in call.args[0])
        strata = json.loads(sample[8])
        self.assertEqual([item["selected_count"] for item in strata], sizes)
        self.assertEqual([item["reserve_count"] for item in strata], [0] * 5)

    def test_impossible_tranco_target_is_not_queued(self):
        with patch.object(routes, "fetch_latest_standard_list", return_value=(b"mock", "synthetic.csv", "TEST123")), \
                patch.object(routes, "parse_tranco", return_value=([], {})):
            response = self.client.post("/run", data={"source_type": "tranco", "title": "Invalid target",
                "tranco_seed": "test-seed", "tranco_count_rank_1_500": "501"})
        self.assertEqual(response.headers["Location"], "/acquisition/new")
        self.connection.cursor.assert_not_called()

    def test_form_has_counts_without_example_caps(self):
        with main.app.test_request_context("/acquisition/new"):
            html = render_template("index.html", wave_available=False)
        page = BeautifulSoup(html, "html.parser")
        for label, _name, _lower, _upper in TRANCO_STRATA:
            field = page.select_one(f"#tranco_count_{label}")
            self.assertEqual(field["min"], "0")
            self.assertEqual(field["step"], "1")
            self.assertNotIn("max", field.attrs)
        self.assertNotIn("maxManualUrls", html)
        self.assertNotIn("Maximum:", html)
        self.assertEqual(page.select_one("#urlCount").get_text(), "0")
        self.assertEqual(main.app.config["MAX_FORM_MEMORY_SIZE"], main.app.config["MAX_CONTENT_LENGTH"])
        self.assertIsNone(main.app.config["MAX_FORM_PARTS"])

    def test_exhausted_report_keeps_target_500_and_success_count_300(self):
        ranking = [(rank, f"site-{rank}.example") for rank in range(1, 501)]
        candidates, strata = sample_tranco(ranking, "TEST123", "census", {"rank_1_500": 500}, 500)
        for candidate in candidates:
            candidate["retry_count"] = 1
        rows = []
        metrics = ("axe_violations", "axe_critical", "axe_serious", "axe_moderate", "axe_minor",
                   "lighthouse_score", "execution_seconds", "images", "dom_nodes")
        for i, candidate in enumerate(candidates):
            rows.append({"id": i + 1, "url": candidate["url"],
                         "status": "completed" if i < 300 else "failed",
                         **dict.fromkeys(metrics, None)})
        experiment = {"id": 73, "title": "Census fixture", "status": "completed", "source_type": "tranco",
                      "urls": "\n".join(item["url"] for item in candidates)}
        self.cursor.fetchone.side_effect = [experiment, {"id": 1}, {"total": 1},
                                             {"candidates": candidates, "strata": strata}]
        self.cursor.fetchall.return_value = rows
        with patch.object(routes, "build_experiment_analysis", return_value={"wave_categories": []}), \
                patch.object(routes, "render_template", return_value="fixture report") as render:
            response = self.client.get("/experiments/73")
        self.assertEqual(response.status_code, 200)
        quality = render.call_args.kwargs["tranco_quality"]
        self.assertEqual(quality["target_size"], 500)
        self.assertEqual(quality["strata"][0]["completed"], 300)
        self.assertEqual(quality["strata"][0]["domains_evaluated"], 500)
        self.assertEqual(quality["reserve_exhausted"], 200)
        self.assertEqual(quality["initial_yield_percent"], 60)
        self.assertIsNone(quality["worst_case_margin_95"])
        template = (APP_DIR / "templates" / "report.html").read_text()
        self.assertIn("Stratum recovery exhausted", template)

    def test_html_archive_can_exceed_old_observation_and_file_caps(self):
        content = io.BytesIO()
        with zipfile.ZipFile(content, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for i in range(10_001):
                archive.writestr(f"page-{i}.html", "<!doctype html><title>Offline test</title>")
        content.seek(0)
        with tempfile.TemporaryDirectory() as directory, patch("dataset_storage.DATASET_ROOT", Path(directory)):
            metadata, rows = import_dataset(FileStorage(stream=content, filename="test.zip"),
                                             [], None, "Large offline corpus", "isolated")
            self.assertEqual(metadata["observations"], 10_001)
            self.assertEqual(len(rows), 10_001)

    def test_legacy_url_storage_is_widened_idempotently(self):
        spec = importlib.util.spec_from_file_location("capacity_database", APP_DIR / "database.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cursor = Mock()
        cursor.fetchone.return_value = ("urls", "text", "NO")
        module.ensure_experiment_url_capacity(cursor)
        cursor.execute.assert_any_call("ALTER TABLE experiments MODIFY COLUMN urls LONGTEXT NOT NULL")
        cursor.reset_mock()
        cursor.fetchone.return_value = ("urls", "longtext", "NO")
        module.ensure_experiment_url_capacity(cursor)
        self.assertEqual(cursor.execute.call_count, 1)


if __name__ == "__main__":
    unittest.main()
