import importlib
import json
import sys
import tempfile
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
experiments = importlib.import_module("routes.experiments")


class ExperimentAnalysisTestCase(unittest.TestCase):
    def test_webaim_comparison_uses_stratified_design_weights(self):
        rows = [
            {"id": 1, "status": "completed", "url": "https://popular.test",
             "axe_violations": 10, "axe_wcag_violations": 1, "dom_nodes": 100,
             "tranco_frame_count": 100, "tranco_selected_count": 100},
            {"id": 2, "status": "completed", "url": "https://long-tail.test",
             "axe_violations": 30, "axe_wcag_violations": 0, "dom_nodes": 300,
             "tranco_frame_count": 900, "tranco_selected_count": 100},
        ]
        with main.app.test_request_context("/"):
            comparison = experiments.build_experiment_analysis(rows)["webaim_comparison"]
        self.assertEqual(comparison["axe_mean"], 0.1)
        self.assertEqual(comparison["dom_mean"], 280.0)
        self.assertEqual(comparison["pages_with_wcag_failures_percent"], 10.0)
        self.assertEqual(comparison["observed_pages_with_wcag_failures_percent"], 50.0)

    def test_webaim_comparison_preserves_category_classifier_provenance(self):
        source = "ollama/gemma4:latest · closed WebAIM 2026 vocabulary · temperature 0"
        rows = [{
            "id": 1, "status": "completed", "url": "https://example.test",
            "axe_violations": 1, "site_category": "Technology",
            "site_category_source": source,
        }]
        with main.app.test_request_context("/"):
            comparison = experiments.build_experiment_analysis(rows)["webaim_comparison"]

        self.assertEqual(comparison["category_sources"], [source])

    def test_webaim_language_rows_use_human_names_and_preserve_codes(self):
        rows = [
            {"id": index, "status": "completed", "url": f"https://{index}.test",
             "axe_violations": index, "language_declared": language}
            for index, language in enumerate(
                ["en-US", "en-AU", "en-PH", "en-EN", "en", None, None, None, None, None], 1
            )
        ]
        with main.app.test_request_context("/"):
            languages = experiments.build_experiment_analysis(rows)["webaim_comparison"]["languages"]

        by_code = {row["code"]: row for row in languages}
        self.assertEqual(by_code["en"]["name"], "English")
        self.assertEqual(by_code["en"]["pages"], 5)
        self.assertEqual(by_code[None]["name"], "No language specified")

    def test_webaim_error_crosswalk_uses_equivalent_axe_rules(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as axe_file:
            json.dump({"violations": [
                {"id": "area-alt"}, {"id": "input-button-name"},
                {"id": "select-name"}, {"id": "object-alt"},
            ]}, axe_file)
            axe_file.flush()
            rows = [{"id": 1, "status": "completed", "url": "https://one.test",
                     "axe_violations": 4, "axe_raw_path": axe_file.name}]
            with main.app.test_request_context("/"):
                errors = experiments.build_experiment_analysis(rows)["webaim_comparison"]["common_errors"]

        by_name = {row["name"]: row["percent"] for row in errors}
        self.assertEqual(by_name["Missing alternative text"], 100.0)
        self.assertEqual(by_name["Empty buttons"], 100.0)
        self.assertEqual(by_name["Missing form labels"], 0.0)

    def test_webaim_benchmark_includes_structure_and_tlds(self):
        rows = [{
            "id": 1, "status": "completed", "url": "https://example.com/",
            "axe_violations": 4, "dom_nodes": 100, "images": 10,
            "images_without_alt": 2, "inputs": 3, "headings": 0, "h1_count": 0,
            "has_main_landmark": False,
        }, {
            "id": 2, "status": "completed", "url": "https://example.org/",
            "axe_violations": 2, "dom_nodes": 200, "images": 20,
            "images_without_alt": 1, "inputs": 5, "headings": 4, "h1_count": 2,
            "has_main_landmark": True,
        }] * 5
        with main.app.test_request_context("/"):
            comparison = experiments.build_experiment_analysis(rows)["webaim_comparison"]

        self.assertEqual(comparison["structure"]["images_mean"], 15.0)
        self.assertEqual(comparison["structure"]["images_missing_alt_percent"], 10.0)
        self.assertEqual(comparison["structure"]["pages_without_headings_percent"], 50.0)
        self.assertEqual([row["name"] for row in comparison["tlds"]], ["org", "com"])
        self.assertLess(comparison["tlds"][0]["difference_percent"], 0)
        self.assertGreater(comparison["tlds"][1]["difference_percent"], 0)
        self.assertEqual(comparison["tlds"][1]["webaim_mean"], 56.2)

    def test_experiment_history_summary_excludes_retired_semantic_usage(self):
        summary = experiments.build_experiments_summary([
            {"status": "completed", "include_semantic": True, "include_wave": True,
             "semantic_provider": "gemini", "processed_urls": 3, "llm_tokens": 1200,
             "wave_credits": 6, "total_cost": 0.31},
            {"status": "failed", "include_semantic": True, "include_wave": False,
             "semantic_provider": "claude", "processed_urls": 1, "llm_tokens": 300,
             "wave_credits": 0, "total_cost": 0.02},
        ])

        self.assertEqual(summary["total_experiments"], 2)
        self.assertEqual(summary["completed_experiments"], 1)
        self.assertNotIn("llm_tokens", summary)
        self.assertNotIn("llm_experiments", summary)
        self.assertEqual(summary["wave_credits"], 6)
        self.assertEqual(summary["total_cost"], 0.33)
        self.assertNotIn("providers", summary)

    def test_analysis_excludes_failed_urls_and_missing_optional_tools(self):
        results = [
            {
                "status": "completed", "url": "https://a.example", "axe_violations": 10,
                "axe_critical": 1, "axe_serious": 2, "axe_moderate": 3, "axe_minor": 4,
                "lighthouse_score": 80, "dom_nodes": 500, "images": 5,
                "execution_seconds": 10, "wave_status": "failed", "wave_errors": 0,
            "semantic_status": "failed", "semantic_findings": [],
                "wave_credits_used": 0, "wave_cost_usd": None,
            },
            {"status": "failed", "url": "https://failed.example"},
        ]

        with main.app.test_request_context("/"):
            analysis = experiments.build_experiment_analysis(results)

        self.assertEqual(analysis["general"]["completed_urls"], 1)
        self.assertEqual(analysis["general"]["failed_urls"], 1)
        self.assertEqual(analysis["coverage"]["wave"], 0)
        self.assertEqual(analysis["coverage"]["semantic"], 0)
        self.assertEqual(analysis["general"]["axe_density_mean"], 20.0)
        self.assertEqual(analysis["general"]["total_wave_credits"], 0)
        self.assertIsNone(analysis["correlations"]["wave_axe"]["spearman"])

    def test_acquisition_signals_do_not_change_completed_measurements(self):
        results = [{
            "id": 7, "status": "completed", "url": "https://source.example/",
            "captured_url": "https://challenge.example/", "page_title": "Verify",
            "acquisition_signals": ["cross_domain_redirect", "security_challenge"],
            "axe_violations": 1, "lighthouse_score": 90, "dom_nodes": 47,
            "images": 0, "execution_seconds": 1,
        }]

        with main.app.test_request_context("/"):
            analysis = experiments.build_experiment_analysis(results)

        self.assertEqual(analysis["general"]["completed_urls"], 1)
        self.assertNotIn("acquisition_review", analysis)

    def test_correlations_report_paired_sample_size(self):
        with main.app.test_request_context("/"):
            record = experiments.correlation_record([1, 2, 3], [3, 2, 1])

        self.assertEqual(record["n"], 3)
        self.assertEqual(record["pearson"], -1.0)
        self.assertEqual(record["spearman"], -1.0)
        self.assertTrue(record["exploratory"])

    def test_semantic_severity_profile_preserves_url_level_counts(self):
        results = [{
            "status": "completed", "url": "https://semantic.example",
            "axe_violations": 1, "dom_nodes": 100, "lighthouse_score": 90,
            "wave_status": "skipped", "semantic_status": "completed",
            "wave_cost_usd": 0.25, "semantic_cost_usd": 0.125,
            "semantic_findings": [
                {"category": "landmark", "severity": "high"},
                {"category": "link_text", "severity": "medium"},
                {"category": "alt_text", "severity": "medium"},
                {"category": "language", "severity": "low"},
            ],
        }]

        with main.app.test_request_context("/"):
            analysis = experiments.build_experiment_analysis(results)

        self.assertEqual(analysis["chart"]["semantic_high"], [1])
        self.assertEqual(analysis["chart"]["semantic_medium"], [2])
        self.assertEqual(analysis["chart"]["semantic_low"], [1])
        self.assertEqual(analysis["chart"]["semantic_unknown"], [0])
        row = analysis["measurement_rows"][0]
        self.assertEqual(row["semantic_findings_count"], 4)
        self.assertEqual(row["semantic_high_count"], 1)
        self.assertEqual(row["semantic_medium_count"], 2)
        self.assertEqual(row["semantic_low_count"], 1)
        self.assertEqual(analysis["measurement_extras"][0]["dom"], 100)
        self.assertEqual(analysis["measurement_extras"][0]["runtime"], None)
        self.assertEqual(analysis["measurement_extras"][0]["total_cost"], 0.375)

    def test_composite_score_uses_equal_weighted_percentile_ranks(self):
        results = [
            {
                "id": 1, "status": "completed", "url": "http://dataset-server:8080/internal/page.html",
                "display_url": "Original page", "dataset_observation_id": 41,
                "axe_violations": 2, "axe_critical": 0, "axe_serious": 1,
                "axe_moderate": 1, "axe_minor": 0, "lighthouse_score": 95,
                "dom_nodes": 1000, "images": 1, "execution_seconds": 1,
                "wave_status": "completed", "wave_aim_score": 9.0,
            },
            {
                "id": 2, "status": "completed", "url": "https://middle.example",
                "axe_violations": 5, "axe_critical": 0, "axe_serious": 2,
                "axe_moderate": 2, "axe_minor": 1, "lighthouse_score": 80,
                "dom_nodes": 1000, "images": 1, "execution_seconds": 1,
                "wave_status": "completed", "wave_aim_score": 6.0,
            },
            {
                "id": 3, "status": "completed", "url": "https://worst.example",
                "axe_violations": 10, "axe_critical": 1, "axe_serious": 3,
                "axe_moderate": 4, "axe_minor": 2, "lighthouse_score": 60,
                "dom_nodes": 1000, "images": 1, "execution_seconds": 1,
                "wave_status": "completed", "wave_aim_score": 3.0,
            },
        ]

        with main.app.test_request_context("/"):
            analysis = experiments.build_experiment_analysis(results)

        self.assertEqual([page["composite_score"] for page in analysis["ranked_pages"]], [100.0, 50.0, 0.0])
        self.assertEqual([page["tool_disagreement"] for page in analysis["ranked_pages"]], [0.0, 0.0, 0.0])
        self.assertEqual(analysis["ranked_pages"][0]["display_name"], "Original page")
        self.assertTrue(analysis["ranked_pages"][0]["is_local_html"])
        self.assertTrue(analysis["ranking_includes_wave"])
        self.assertEqual(analysis["ranking_tool_count"], 3)

    def test_report_charts_use_global_page_names_not_technical_urls(self):
        results = [{
            "id": 1,
            "status": "completed",
            "url": "http://dataset-server:8080/internal/generated/gemini/html/template-no.html",
            "display_url": "Gemini – HTML – no template",
            "display_name": "Gemini – HTML – no template",
            "dataset_observation_id": 41,
            "axe_violations": 2,
            "lighthouse_score": 95,
            "dom_nodes": 100,
            "wave_status": "skipped",
        }]

        with main.app.test_request_context("/"):
            analysis = experiments.build_experiment_analysis(results)

        self.assertEqual(analysis["chart"]["labels"], ["Gemini – HTML – no template"])
        self.assertNotIn("dataset-server", analysis["chart"]["labels"][0])

    def test_composite_score_requires_three_complete_three_tool_results(self):
        values = experiments.comparative_percentiles([10, 20], higher_is_better=False)
        self.assertEqual(values, [None, None])

    def test_two_complete_pages_do_not_produce_a_cross_tool_ranking(self):
        results = [
            {
                "id": index, "status": "completed", "url": f"https://{index}.example",
                "axe_violations": index, "axe_critical": 0, "axe_serious": index,
                "axe_moderate": 0, "axe_minor": 0, "lighthouse_score": 100 - index,
                "dom_nodes": 1000, "wave_status": "completed", "wave_aim_score": 10 - index,
            }
            for index in (1, 2)
        ]

        with main.app.test_request_context("/"):
            analysis = experiments.build_experiment_analysis(results)

        self.assertEqual(analysis["ranking_mode"], "unavailable")
        self.assertEqual(analysis["coverage"]["composite"], 0)
        self.assertTrue(all(page["composite_score"] is None for page in analysis["ranked_pages"]))

    def test_composite_ranking_uses_axe_and_lighthouse_without_wave(self):
        results = [
            {
                "id": 1, "status": "completed", "url": "https://lower.example",
                "axe_violations": 2, "axe_critical": 0, "axe_serious": 1,
                "axe_moderate": 0, "axe_minor": 1, "lighthouse_score": 95,
                "dom_nodes": 1000, "wave_status": "skipped",
            },
            {
                "id": 2, "status": "completed", "url": "https://middle.example",
                "axe_violations": 4, "axe_critical": 1, "axe_serious": 2,
                "axe_moderate": 1, "axe_minor": 0, "lighthouse_score": 80,
                "dom_nodes": 1000, "wave_status": "skipped",
            },
            {
                "id": 3, "status": "completed", "url": "https://worst.example",
                "axe_violations": 8, "axe_critical": 1, "axe_serious": 4,
                "axe_moderate": 2, "axe_minor": 1, "lighthouse_score": 60,
                "dom_nodes": 1000, "wave_status": "skipped",
            },
        ]

        with main.app.test_request_context("/"):
            analysis = experiments.build_experiment_analysis(results)

        self.assertEqual(analysis["ranking_mode"], "composite")
        self.assertFalse(analysis["ranking_includes_wave"])
        self.assertEqual(analysis["ranking_tool_count"], 2)
        self.assertEqual(analysis["ranked_pages"][0]["url"], "https://lower.example")
        self.assertEqual([page["composite_score"] for page in analysis["ranked_pages"]], [100.0, 50.0, 0.0])
        self.assertEqual(analysis["chart"]["axe_critical_only"], [0, 1, 1])
        self.assertEqual(analysis["correlations"]["axe_critical_lighthouse"]["n"], 3)

    def test_tranco_groups_report_descriptive_distributions(self):
        rows = [
            {"id": 1, "status": "completed", "url": "https://a.example",
             "axe_violations": 0, "axe_critical": 0, "axe_serious": 0,
             "axe_moderate": 0, "axe_minor": 0, "lighthouse_score": 95,
             "dom_nodes": 100, "wave_status": "skipped"},
            {"id": 2, "status": "completed", "url": "https://b.example",
             "axe_violations": 4, "axe_critical": 4, "axe_serious": 0,
             "axe_moderate": 0, "axe_minor": 0, "lighthouse_score": 75,
             "dom_nodes": 100, "wave_status": "skipped"},
        ]
        for row in rows:
            row["tranco_stratum"] = "Global top 500"
        group = experiments.build_experiment_analysis(rows)["tranco_strata"][0]
        self.assertEqual(group["n"], 2)
        self.assertEqual(group["axe_issue_share_percent"], 100.0)
        self.assertEqual(group["axe_mean"], 2.0)
        self.assertEqual(group["lighthouse_mean"], 85.0)
        self.assertEqual(group["critical"]["median"], 2.0)
        self.assertEqual(group["critical"]["whisker_low"], 0.0)
        self.assertEqual(group["critical"]["whisker_high"], 4.0)

    def test_composite_score_uses_raw_axe_issues_not_density(self):
        results = [
            {"id": 1, "status": "completed", "url": "https://a.example", "axe_violations": 3,
             "dom_nodes": 100, "lighthouse_score": 90, "wave_status": "completed", "wave_aim_score": 9},
            {"id": 2, "status": "completed", "url": "https://b.example", "axe_violations": 5,
             "dom_nodes": 10000, "lighthouse_score": 80, "wave_status": "completed", "wave_aim_score": 8},
            {"id": 3, "status": "completed", "url": "https://c.example", "axe_violations": 8,
             "dom_nodes": 1000, "lighthouse_score": 70, "wave_status": "completed", "wave_aim_score": 7},
        ]

        with main.app.test_request_context("/"):
            analysis = experiments.build_experiment_analysis(results)

        self.assertEqual(analysis["ranked_pages"][0]["url"], "https://a.example")
        self.assertEqual(analysis["ranked_pages"][0]["composite_score"], 100.0)

    def test_delete_experiment_removes_related_database_records(self):
        statements = []

        class Cursor:
            def execute(self, statement, parameters=None):
                statements.append(" ".join(statement.split()))

            def fetchone(self):
                return {"id": 42, "title": "Study", "status": "completed"}

            def close(self):
                pass

        class Connection:
            def cursor(self, dictionary=False):
                return Cursor()

            def commit(self):
                statements.append("COMMIT")

            def rollback(self):
                statements.append("ROLLBACK")

            def close(self):
                pass

        with patch.object(experiments, "get_connection", return_value=Connection()):
            response = main.app.test_client().post("/experiments/42/delete")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(any("DELETE FROM experiment_results" in item for item in statements))
        self.assertTrue(any("DELETE FROM experiment_environment" in item for item in statements))
        self.assertTrue(any("DELETE FROM experiments" in item for item in statements))
        self.assertIn("COMMIT", statements)

    def test_dependent_remediations_block_deletion_with_ids_and_next_steps(self):
        from unittest.mock import MagicMock
        conn = MagicMock(); cursor = conn.cursor.return_value
        cursor.fetchone.side_effect = [
            {'id':42,'title':'Study','status':'completed'}, {'total':125},
        ]
        cursor.fetchall.return_value = [{'id':value} for value in range(659,669)]
        client = main.app.test_client()
        with patch.object(experiments,'get_connection',return_value=conn):
            response = client.post('/experiments/42/delete')
        self.assertEqual(response.status_code,302)
        with client.session_transaction() as session:
            message = session['_flashes'][-1][1]
        self.assertIn('125 remediation',message)
        self.assertIn('#659',message)
        self.assertIn('Remediation runs',message)
        self.assertIn('comparisons',message)
        self.assertIn('Nothing was deleted',message)
        self.assertIn('LIMIT 10',cursor.execute.call_args.args[0])
        for call in cursor.execute.call_args_list:
            self.assertTrue(call.args[0].lstrip().startswith('SELECT'))
        conn.commit.assert_not_called()
        cursor.close.assert_called_once(); conn.close.assert_called_once()

    def test_running_deletion_explains_wait_or_pause_without_database_writes(self):
        from unittest.mock import MagicMock
        for status in ('queued','running'):
            conn = MagicMock(); cursor = conn.cursor.return_value
            cursor.fetchone.return_value = {'id':42,'title':'Study','status':status}
            client=main.app.test_client()
            with patch.object(experiments,'get_connection',return_value=conn):
                client.post('/experiments/42/delete')
            with client.session_transaction() as session:
                message=session['_flashes'][-1][1]
            self.assertIn('#42',message); self.assertIn('pause',message)
            self.assertIn('current page',message)
            self.assertEqual(cursor.execute.call_count,1)
            conn.commit.assert_not_called()

    def test_database_deletion_failure_rolls_back_and_explains_recovery(self):
        from unittest.mock import MagicMock
        conn = MagicMock(); cursor = conn.cursor.return_value
        cursor.fetchone.side_effect = [{'id':42,'title':'Study','status':'completed'}, {'total':0}]
        cursor.execute.side_effect = [None,None,RuntimeError('database failure')]
        client=main.app.test_client()
        with patch.object(experiments,'get_connection',return_value=conn), \
                patch.object(experiments.shutil,'rmtree') as remove, \
                patch.object(main.app.logger,'exception'):
            client.post('/experiments/42/delete')
        with client.session_transaction() as session:
            message=session['_flashes'][-1][1]
        self.assertIn('rolled back',message); self.assertIn('Refresh',message)
        self.assertIn('administrator',message); self.assertIn('#42',message)
        conn.rollback.assert_called_once(); conn.commit.assert_not_called(); remove.assert_not_called()

    def test_failed_experiment_can_resume_without_deleting_results(self):
        statements = []
        rows = iter((
            {"id": 42, "status": "failed", "urls": "https://a.example/\nhttps://b.example/"},
            {"processed": 1},
        ))

        class Cursor:
            def execute(self, statement, parameters=None):
                statements.append(" ".join(statement.split()))

            def fetchone(self):
                return next(rows)

            def close(self):
                pass

        class Connection:
            def cursor(self, dictionary=False):
                return Cursor()

            def commit(self):
                statements.append("COMMIT")

            def rollback(self):
                statements.append("ROLLBACK")

            def close(self):
                pass

        with patch.object(experiments, "get_connection", return_value=Connection()):
            response = main.app.test_client().post("/experiments/42/resume")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(any("SET status='queued'" in item for item in statements))
        self.assertFalse(any("DELETE FROM experiment_results" in item for item in statements))
        self.assertIn("COMMIT", statements)

    def test_running_experiment_can_pause_without_deleting_results(self):
        statements = []

        class Cursor:
            def execute(self, statement, parameters=None):
                statements.append(" ".join(statement.split()))

            def fetchone(self):
                return {"id": 42, "status": "running"}

            def close(self):
                pass

        class Connection:
            def cursor(self, dictionary=False):
                return Cursor()

            def commit(self):
                statements.append("COMMIT")

            def rollback(self):
                statements.append("ROLLBACK")

            def close(self):
                pass

        with patch.object(experiments, "get_connection", return_value=Connection()):
            response = main.app.test_client().post(
                "/experiments/42/pause", data={"return_to": "list"}
            )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/evaluations"))
        self.assertTrue(any("SET status='paused'" in item for item in statements))
        self.assertFalse(any("DELETE FROM experiment_results" in item for item in statements))
        self.assertIn("COMMIT", statements)

    def test_removing_only_url_deletes_the_empty_experiment(self):
        statements = []
        one_rows = iter((
            {"id": 42, "status": "completed"},
            {"total": 1},
        ))

        class Cursor:
            def execute(self, statement, parameters=None):
                statements.append(" ".join(statement.split()))

            def fetchone(self):
                return next(one_rows)

            def fetchall(self):
                return [{"id": 7, "screenshot_path": None, "axe_raw_path": None,
                         "lighthouse_raw_path": None, "wave_raw_path": None,
                         "semantic_raw_path": None}]

            def close(self):
                pass

        class Connection:
            def cursor(self, dictionary=False):
                return Cursor()

            def commit(self):
                statements.append("COMMIT")

            def rollback(self):
                statements.append("ROLLBACK")

            def close(self):
                pass

        with (
            patch.object(experiments, "get_connection", return_value=Connection()),
            patch.object(experiments.os.path, "isdir", return_value=False),
        ):
            response = main.app.test_client().post(
                "/experiments/42/urls/remove", data={"result_ids": "7"}
            )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(any("DELETE FROM experiment_results WHERE experiment_id = %s" in item for item in statements))
        self.assertTrue(any("DELETE FROM experiment_environment" in item for item in statements))
        self.assertTrue(any("DELETE FROM experiments" in item for item in statements))
        self.assertFalse(any("UPDATE experiments" in item for item in statements))
        self.assertIn("COMMIT", statements)

    def test_legacy_manage_url_route_opens_unified_manager(self):
        response = main.app.test_client().get("/experiments/42/urls")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/experiments/compose?target=42", response.location)

    def test_clear_experiments_requires_exact_confirmation(self):
        with patch.object(experiments, "get_connection") as connection:
            response = main.app.test_client().post(
                "/configuration/clear-experiments",
                data={"confirmation_text": "DELETE"},
            )

        self.assertEqual(response.status_code, 302)
        connection.assert_not_called()

    def test_clear_experiments_deletes_all_related_records(self):
        statements = []
        rows = iter(({"total": 0}, {"total": 3}))

        class Cursor:
            def execute(self, statement, parameters=None):
                statements.append(" ".join(statement.split()))

            def fetchone(self):
                return next(rows)

            def close(self):
                pass

        class Connection:
            def cursor(self, dictionary=False):
                return Cursor()

            def commit(self):
                statements.append("COMMIT")

            def rollback(self):
                statements.append("ROLLBACK")

            def close(self):
                pass

        with (
            patch.object(experiments, "get_connection", return_value=Connection()),
            patch.object(experiments.os.path, "isdir", return_value=False),
            patch.object(experiments, "clear_dataset_storage") as clear_storage,
        ):
            response = main.app.test_client().post(
                "/configuration/clear-experiments",
                data={"confirmation_text": "DELETE ALL EXPERIMENTS"},
            )

        self.assertEqual(response.status_code, 302)
        self.assertIn("DELETE FROM experiment_results", statements)
        self.assertIn("DELETE FROM experiment_environment", statements)
        self.assertIn("DELETE FROM experiments", statements)
        self.assertIn("ALTER TABLE experiments AUTO_INCREMENT = 1", statements)
        self.assertIn("ALTER TABLE experiment_results AUTO_INCREMENT = 1", statements)
        self.assertIn("ALTER TABLE experiment_environment AUTO_INCREMENT = 1", statements)
        self.assertIn("COMMIT", statements)
        clear_storage.assert_called_once_with()

    def test_empty_experiment_list_renders_without_error(self):
        class Cursor:
            def execute(self, statement, parameters=None):
                pass

            def fetchall(self):
                return []

            def close(self):
                pass

        class Connection:
            def cursor(self, dictionary=False):
                return Cursor()

            def close(self):
                pass

        with patch.object(experiments, "get_connection", return_value=Connection()):
            response = main.app.test_client().get("/experiments")

        self.assertEqual(response.status_code, 200)

    def test_unexpected_errors_render_friendly_page(self):
        with patch.object(experiments, "get_connection", side_effect=RuntimeError("test failure")):
            response = main.app.test_client().get("/experiments")

        self.assertEqual(response.status_code, 500)
        self.assertIn(b"We could not display this page", response.data)
        self.assertNotIn(b"Internal Server Error", response.data)

    def test_paired_analysis_uses_manifest_conditions_and_direction(self):
        rows = [
            {"status": "completed", "pair_key": "case-1", "condition_label": "original",
             "display_url": "case-1-original", "stratum": "forms",
             "axe_violations": 10, "lighthouse_score": 70},
            {"status": "completed", "pair_key": "case-1", "condition_label": "corrected",
             "display_url": "case-1-corrected", "stratum": "forms",
             "axe_violations": 4, "lighthouse_score": 88},
            {"status": "completed", "pair_key": "incomplete", "condition_label": "original",
             "axe_violations": 2, "lighthouse_score": 90},
        ]

        paired = experiments.build_paired_analysis(rows)

        self.assertEqual(paired["candidate_pairs"], 2)
        self.assertEqual(paired["complete_pairs"], 1)
        self.assertEqual(paired["axe_mean_reduction"], 6)
        self.assertEqual(paired["lighthouse_mean_gain"], 18)
        self.assertEqual(paired["axe_improved"], 1)

    def test_manual_site_category_updates_every_observation_for_normalized_url(self):
        statements = []

        class Cursor:
            def execute(self, statement, parameters=None):
                statements.append((" ".join(statement.split()), parameters))

            def fetchone(self):
                return {"id": 17, "normalized_url": "https://example.com/"}

            def close(self):
                pass

        class Connection:
            def cursor(self, dictionary=False):
                return Cursor()

            def commit(self):
                statements.append(("COMMIT", None))

            def close(self):
                pass

        with patch.object(experiments, "get_connection", return_value=Connection()):
            response = main.app.test_client().post(
                "/urls/17/site-category", json={"site_category": "Education"}
            )

        self.assertEqual(response.status_code, 200)
        update = next(item for item in statements if "UPDATE experiment_results" in item[0])
        self.assertIn("WHERE normalized_url=%s", update[0])
        self.assertEqual(update[1], (
            "Education", "manual · closed WebAIM 2026 vocabulary",
            "https://example.com/",
        ))
        self.assertIn(("COMMIT", None), statements)

    def test_manual_site_category_rejects_values_outside_webaim_vocabulary(self):
        with patch.object(experiments, "get_connection") as connection:
            response = main.app.test_client().post(
                "/urls/17/site-category", json={"site_category": "Made up"}
            )

        self.assertEqual(response.status_code, 400)
        connection.assert_not_called()

    def test_manage_urls_auto_categorization_queues_persistent_local_job(self):
        statements = []
        rows = iter((None, {"total": 3}))

        class Cursor:
            def execute(self, statement, parameters=None):
                statements.append((" ".join(statement.split()), parameters))

            def fetchone(self):
                return next(rows)

            def close(self):
                pass

        class Connection:
            def cursor(self, dictionary=False):
                return Cursor()

            def commit(self):
                statements.append(("COMMIT", None))

            def close(self):
                pass

        with (
            patch.object(experiments, "get_settings", return_value={}),
            patch.object(experiments, "local_configuration", return_value={"model": "gemma4"}),
            patch.object(experiments, "get_connection", return_value=Connection()),
        ):
            response = main.app.test_client().post(
                "/urls/auto-categorize", json={"model": "local"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["job"]["status"], "queued")
        self.assertTrue(any("INSERT INTO url_category_jobs" in item[0] for item in statements))
        self.assertIn(("COMMIT", None), statements)


if __name__ == "__main__":
    unittest.main()
