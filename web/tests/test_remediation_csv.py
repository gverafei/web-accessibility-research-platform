import copy
import csv
from decimal import Decimal
from io import StringIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from remediation_csv import FIELDS, remediation_csv


class RemediationCsvTests(unittest.TestCase):
    def setUp(self):
        self.run = {'id': 21, 'source_result_id': 11, 'title': 'Repair, "UV" á',
                    'status': 'completed_with_warnings', 'accepted_iteration_id': 31,
                    'total_cost_usd': Decimal('0.00298868'), 'execution_seconds': 26.0,
                    'total_input_tokens': 100, 'total_output_tokens': 20,
                    'max_cost_usd': Decimal('0.25'), 'max_execution_seconds': 360,
                    'use_rag': True, 'error_message': 'Timeout after best candidate'}
        self.source = {'id': 11, 'experiment_id': 5, 'url': 'https://www.uv.mx/',
                       'axe_violations': 24, 'axe_wcag_violations': 14,
                       'axe_best_practice_issues': 10, 'lighthouse_score': 93}
        self.iterations = [
            {'id': 31, 'iteration_number': 1, 'decision': 'refine',
             'decision_reason': 'Targets not met', 'generator_model': 'openai/gpt-6-luna',
             'axe_violations': 10, 'axe_wcag_violations': 3, 'axe_best_practice_issues': 7,
             'lighthouse_score': 93, 'wave_aim_score': None, 'cost_usd': Decimal('0.00298868'),
             'execution_seconds': 26.0, 'input_tokens': 100, 'output_tokens': 20,
             'strategy_json': json.dumps({'rag': {'enabled': True, 'retrieved': []},
                 'content_retention': {'text_percent': 100, 'links_percent': 90, 'images_percent': 80}})},
            {'id': 32, 'iteration_number': 2, 'decision': 'rollback', 'axe_wcag_violations': 0,
             'axe_best_practice_issues': 0, 'lighthouse_score': None,
             'strategy_json': {'rag': {'retrieved': [{'rule_id': 'one'}, {'rule_id': 'two'}]}}},
        ]

    def rows(self, text):
        return list(csv.DictReader(StringIO(text.lstrip('\ufeff'))))

    def test_original_and_all_iterations_keep_wcag_costs_and_retained_link(self):
        before = copy.deepcopy((self.run, self.source, self.iterations))
        text = remediation_csv(self.run, self.source, self.iterations)
        self.assertTrue(text.startswith('\ufeff'))
        rows = self.rows(text)
        self.assertEqual(tuple(rows[0]), FIELDS)
        self.assertEqual([row['row_kind'] for row in rows], ['original', 'iteration', 'iteration'])
        self.assertEqual([row['axe_issue_instances'] for row in rows], ['14', '3', '0'])
        self.assertEqual([row['axe_best_practice_issues'] for row in rows], ['10', '7', '0'])
        self.assertEqual([row['is_retained'] for row in rows], ['False', 'True', 'False'])
        self.assertEqual(rows[1]['cost_usd'], '0.00298868')
        self.assertEqual(rows[1]['run_total_cost_usd'], '0.00298868')
        self.assertEqual(rows[1]['run_max_execution_seconds'], '360')
        self.assertEqual(rows[1]['content_retention_percent'], '90.0')
        self.assertEqual(rows[1]['run_title'], 'Repair, "UV" á')
        self.assertEqual(rows[2]['run_error_message'], 'Timeout after best candidate')
        self.assertEqual((self.run, self.source, self.iterations), before)

    def test_null_metrics_and_missing_rag_are_not_measured_zeros(self):
        self.source['axe_wcag_violations'] = None
        self.run['accepted_iteration_id'] = None
        self.iterations[1]['strategy_json'] = 'invalid json'
        rows = self.rows(remediation_csv(self.run, self.source, self.iterations))
        self.assertEqual(rows[0]['axe_issue_instances'], '')
        self.assertEqual(rows[2]['lighthouse_score'], '')
        self.assertEqual(rows[1]['wave_aim_score'], '')
        self.assertEqual(rows[1]['rag_used'], 'False')
        self.assertEqual(rows[1]['rag_example_count'], '0')
        self.assertEqual(rows[2]['rag_used'], '')
        self.assertEqual(rows[2]['rag_example_count'], '')
        self.assertEqual(rows[1]['is_retained'], '')

    def test_rag_enabled_is_distinct_from_retrieved_examples(self):
        rows = self.rows(remediation_csv(self.run, self.source, self.iterations))
        self.assertEqual(rows[1]['run_use_rag'], 'True')
        self.assertEqual(rows[1]['rag_used'], 'False')
        self.assertEqual(rows[2]['rag_used'], 'True')
        self.assertEqual(rows[2]['rag_example_count'], '2')

    def test_recovered_accounting_is_blank_while_run_totals_remain(self):
        self.iterations[0]['strategy_json'] = {'recovery': {'source': 'old export'}}
        rows = self.rows(remediation_csv(self.run, self.source, self.iterations))
        self.assertEqual(rows[1]['evidence_recovered'], 'True')
        for field in ('input_tokens', 'output_tokens', 'cost_usd', 'execution_seconds',
                      'run_total_input_tokens', 'run_total_output_tokens'):
            self.assertEqual(rows[1][field], '', field)
        self.assertEqual(rows[1]['run_total_cost_usd'], '0.00298868')
        self.assertEqual(rows[1]['run_execution_seconds'], '26.0')

    def test_formula_like_text_is_escaped_but_numeric_values_are_unchanged(self):
        for title in ('=1+1', ' +SUM(1,2)', '-1+1', '@command', '\tformula', '\nformula'):
            with self.subTest(title=title):
                self.run['title'] = title
                self.iterations[0]['dom_distance'] = -1.5
                rows = self.rows(remediation_csv(self.run, self.source, self.iterations))
                self.assertEqual(rows[0]['run_title'], "'" + title)
                self.assertEqual(rows[1]['dom_distance_percent'], '-1.5')

    def test_no_iterations_still_exports_original_and_run_failure(self):
        self.run['status'] = 'failed'
        rows = self.rows(remediation_csv(self.run, self.source, []))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['run_status'], 'failed')

    def route_app(self):
        from flask import Flask
        from routes.remediation import remediation_bp
        app = Flask(__name__)
        app.register_blueprint(remediation_bp)
        return app

    def test_route_downloads_only_recorded_data_with_no_external_calls_or_writes(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value
        cursor.fetchone.side_effect = [self.run, self.source]
        cursor.fetchall.return_value = self.iterations
        with patch('routes.remediation.get_connection', return_value=conn), \
             patch('requests.post', side_effect=AssertionError('No paid calls')):
            response = self.route_app().test_client().get('/remediation/21/csv')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/csv')
        self.assertEqual(response.headers['Content-Disposition'], 'attachment; filename="remediation-21.csv"')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(len(self.rows(response.data.decode('utf-8-sig'))), 3)
        for call in cursor.execute.call_args_list:
            self.assertTrue(call.args[0].startswith('SELECT'))
        conn.commit.assert_not_called()
        cursor.close.assert_called_once()
        conn.close.assert_called_once()

    def test_route_missing_run_or_source_is_404_and_closes_database(self):
        for records in ([None], [self.run, None]):
            with self.subTest(records=records):
                conn = MagicMock()
                cursor = conn.cursor.return_value
                cursor.fetchone.side_effect = records
                with patch('routes.remediation.get_connection', return_value=conn):
                    response = self.route_app().test_client().get('/remediation/21/csv')
                self.assertEqual(response.status_code, 404)
                cursor.fetchall.assert_not_called()
                cursor.close.assert_called_once()
                conn.close.assert_called_once()

    def test_route_closes_database_if_iteration_query_fails(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value
        cursor.fetchone.side_effect = [self.run, self.source]
        cursor.fetchall.side_effect = RuntimeError('database unavailable')
        app = self.route_app()
        app.testing = True
        with patch('routes.remediation.get_connection', return_value=conn):
            with self.assertRaisesRegex(RuntimeError, 'database unavailable'):
                app.test_client().get('/remediation/21/csv')
        cursor.close.assert_called_once()
        conn.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
