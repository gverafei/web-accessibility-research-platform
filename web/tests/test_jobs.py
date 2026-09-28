import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from jobs import (begin_tranco_attempt, finish_tranco_attempt,
                  pending_evaluation_urls, record_evaluator_interruption,
                  request_evaluation)


class EvaluationRequestTests(unittest.TestCase):
    def test_resume_skips_completed_and_failed_results_but_not_interrupted_url(self):
        urls = ["https://complete.test/", "https://failed.test/", "https://pending.test/"]
        existing = {
            urls[0]: {"status": "completed", "source_snapshot_path": "/results/source.html"},
            urls[1]: {"status": "failed", "source_snapshot_path": None},
        }
        self.assertEqual(pending_evaluation_urls(urls, existing), [urls[2]])

    def test_evaluator_outage_requeues_without_creating_failed_result(self):
        cursor = Mock()
        record_evaluator_interruption(cursor, 131, 77, ConnectionError("evaluator down"), 10.0, "end")
        self.assertEqual(cursor.execute.call_count, 2)
        attempt_sql, attempt_values = cursor.execute.call_args_list[0].args
        self.assertIn("status='interrupted'", attempt_sql)
        self.assertEqual(attempt_values, ("end", 10.0, "evaluator down", 77))
        experiment_sql, experiment_values = cursor.execute.call_args_list[1].args
        self.assertIn("status='queued'", experiment_sql)
        self.assertEqual(experiment_values, (131,))

    def test_tranco_attempt_start_is_persisted_before_evaluation(self):
        cursor = Mock(lastrowid=77)
        cursor.fetchone.return_value = {"number": 2}
        self.assertEqual(begin_tranco_attempt(cursor, 130, "https://example.com/", "start"), 77)
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertEqual(cursor.execute.call_args.args[1],
                         (130, "https://example.com/", 3, "start"))

    def test_failed_tranco_attempt_keeps_time_and_error(self):
        cursor = Mock()
        finish_tranco_attempt(cursor, 77, {
            "status": "failed", "error": "net::ERR_NAME_NOT_RESOLVED",
            "execution_seconds": 12.0,
        }, 14.5, "end")
        params = cursor.execute.call_args.args[1]
        self.assertEqual(params[0], "failed")
        self.assertEqual(params[2:5], (14.5, 12.0, "dns_resolution"))
        self.assertEqual(params[-1], 77)

    def test_retries_a_transient_evaluator_disconnect(self):
        app = Mock(config={"EVALUATOR_URL": "http://evaluator:3000"})
        successful = Mock()
        successful.raise_for_status.return_value = None
        successful.json.return_value = {"results": []}
        import requests
        with patch("jobs.requests.post", side_effect=[
            requests.ConnectionError("closed"), successful,
        ]) as post, patch("jobs.time.sleep") as sleep:
            self.assertEqual(request_evaluation(app, {"urls": ["https://example.com"]}), {"results": []})
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(5)

    def test_raises_after_three_disconnects(self):
        app = Mock(config={"EVALUATOR_URL": "http://evaluator:3000"})
        import requests
        with patch("jobs.requests.post", side_effect=requests.ConnectionError("closed")) as post, patch("jobs.time.sleep"):
            with self.assertRaises(requests.ConnectionError):
                request_evaluation(app, {"urls": ["https://example.com"]})
        self.assertEqual(post.call_count, 3)


if __name__ == "__main__":
    unittest.main()
