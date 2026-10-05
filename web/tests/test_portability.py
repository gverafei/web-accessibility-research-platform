import importlib
import base64
import sys
import types
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

if "database" not in sys.modules:
    database_stub = types.ModuleType("database")
    database_stub.init_db = lambda: None
    database_stub.get_connection = lambda: None
    sys.modules["database"] = database_stub

portability = importlib.import_module("result_portability")


class ResultPortabilityTestCase(unittest.TestCase):
    def test_portable_package_includes_frozen_html_evidence(self):
        self.assertIn("source_snapshot_path", portability.ARTIFACT_COLUMNS)
        self.assertIn("response_source_path", portability.ARTIFACT_COLUMNS)

    def test_url_normalization_removes_fragment_default_port_and_trailing_slash(self):
        self.assertEqual(
            portability.normalize_url("HTTPS://Example.COM:443/research/#section"),
            "https://example.com/research",
        )

    def test_missing_url_protocol_defaults_to_https(self):
        self.assertEqual(
            portability.ensure_http_scheme("www.example.com/path"),
            "https://www.example.com/path",
        )
        self.assertEqual(
            portability.normalize_url("www.example.com/path/"),
            "https://www.example.com/path",
        )
        self.assertEqual(
            portability.ensure_http_scheme("http://www.example.com"),
            "http://www.example.com",
        )

    def test_evaluation_signature_changes_with_research_protocol(self):
        settings = {
            "wave_report_type": "2", "page_load_timeout_ms": "60000",
            "network_idle_timeout_ms": "15000", "page_settle_delay_ms": "2000",
            "dom_stability_window_ms": "1500", "dom_stability_timeout_ms": "10000",
            "enable_lazy_load_scroll": "true", "scroll_step_px": "700",
            "scroll_delay_ms": "350", "max_scroll_steps": "40",
        }
        baseline = portability.evaluation_signature(
            settings, False, False, None, None, "wcag22aa"
        )
        changed = dict(settings, scroll_step_px="900")
        self.assertNotEqual(
            baseline,
            portability.evaluation_signature(
                changed, False, False, None, None, "wcag22aa"
            ),
        )

    def test_portable_payload_validation_is_all_or_nothing(self):
        valid = {
            "format": "warp-experiment", "version": 3, "experiment": {}, "environment": [],
            "results": [{"data": {"url": "https://example.org/", "status": "completed"},
                         "artifacts": {"axe_raw_path": {"filename": "axe.json", "base64": base64.b64encode(b"{}").decode()}}}],
        }
        self.assertEqual(len(portability.validate_portable_payload(valid)), 1)

        invalid = dict(valid)
        invalid["results"] = list(valid["results"]) + [
            {"data": {"url": "not-a-url"}, "artifacts": {}}
        ]
        with self.assertRaises(ValueError):
            portability.validate_portable_payload(invalid)

    def test_portable_payload_rejects_corrupt_embedded_artifact(self):
        payload = {
            "format": "warp-experiment", "version": 3, "experiment": {}, "environment": [],
            "results": [{"data": {"url": "https://example.org/"},
                         "artifacts": {"axe_raw_path": {"filename": "axe.json", "base64": "not base64!"}}}],
        }
        with self.assertRaises(ValueError):
            portability.validate_portable_payload(payload)

    def test_interfaces_expose_cache_composition_and_portable_json(self):
        index = (APP_DIR / "templates" / "index.html").read_text(encoding="utf-8")
        history = (APP_DIR / "templates" / "experiments.html").read_text(encoding="utf-8")
        navigation = (APP_DIR / "templates" / "base.html").read_text(encoding="utf-8")
        compose = (APP_DIR / "templates" / "compose.html").read_text(encoding="utf-8")
        import_page = (APP_DIR / "templates" / "import.html").read_text(encoding="utf-8")
        report = (APP_DIR / "templates" / "report.html").read_text(encoding="utf-8")

        self.assertIn('name="reuse_cached_results" checked', index)
        self.assertIn("Acquisition source", index)
        self.assertIn("Optional evaluators", index)
        self.assertIn("Stored-result reuse", index)
        self.assertIn("compose_experiment", history)
        self.assertNotIn('name="experiment_file"', history)
        self.assertNotIn('<pre class="small mb-0">{{ experiment.urls }}</pre>', history)
        self.assertNotIn('<details class="frozen-results">', history)
        self.assertIn('experiment.urls.splitlines()|length', history)
        self.assertIn('experiment.failed_urls', history)
        self.assertIn("compose_experiment", navigation)
        self.assertIn("import_experiment_json", navigation)
        self.assertIn('data-theme="{{ ui_theme }}"', navigation)
        self.assertIn('data-theme-choice="{{ ui_theme }}"', navigation)
        self.assertIn("prefers-color-scheme: dark", navigation)
        self.assertIn('name="experiment_file"', import_page)
        self.assertIn('accept=".warp,application/octet-stream"', import_page)
        self.assertNotIn('name="import_target"', import_page)
        self.assertIn("import-progress", import_page)
        self.assertIn("portable_export(url_for('experiments.download_experiment_json'", history)
        self.assertIn("Export data", (APP_DIR / 'templates/_portable_export.html').read_text())
        self.assertIn("warp-export", (APP_DIR / 'templates/_portable_export.html').read_text())
        self.assertIn("evaluation-frozen", history)
        self.assertIn("frozen observations", history)
        self.assertIn('name="result_ids"', compose)
        self.assertNotIn("Replace matching URLs", compose)
        self.assertNotIn("replace_existing", compose)
        self.assertIn("dataset-target-inline", compose)
        self.assertIn("dataset-empty-list", compose)
        self.assertIn("targetPicker", compose)
        self.assertIn("sourceExperiment", compose)
        self.assertIn("Optional — If left empty, Combined evaluation + the current date and time will be used", compose)
        self.assertIn("submitInPlace", compose)
        self.assertIn("row.draggable=!!dropZone&&!disabled", compose)
        self.assertIn("datasetFeedback", compose)
        self.assertIn("result-just-added", compose)
        self.assertIn("Pages in destination", compose)
        self.assertIn("experiment_report", compose)
        self.assertIn('data-sort="url"', compose)
        self.assertIn('data-sort="url"', compose)
        header=(APP_DIR/'templates'/'_evaluation_report_header.html').read_text()
        self.assertIn("_evaluation_report_header.html", report)
        self.assertIn("download_experiment_json", header)
        self.assertIn("portable_export(url_for('experiments.download_experiment_json'", header)
        self.assertIn("Frozen-result provenance", report)
        self.assertIn("pager-first", report)
        self.assertIn("pager-last", report)
        self.assertIn("tranco-provenance", report)


if __name__ == "__main__":
    unittest.main()
