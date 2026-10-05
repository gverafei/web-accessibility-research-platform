"""Visible count units follow the existing records-versus-unique-URLs contracts."""
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup
from flask import render_template, render_template_string, session

APP_DIR = Path(__file__).resolve().parents[1] / 'app'
sys.path.insert(0, str(APP_DIR))
if 'database' not in sys.modules:
    stub = types.ModuleType('database')
    stub.init_db = lambda: None
    stub.get_connection = lambda: None
    sys.modules['database'] = stub

from main import app
from routes.experiments import build_experiments_summary


class PageCountLabelTests(unittest.TestCase):
    def test_dashboard_completed_count_and_evaluation_all_results_have_distinct_labels(self):
        dashboard = BeautifulSoup((APP_DIR / 'templates/dashboard.html').read_text(), 'html.parser')
        evaluations = BeautifulSoup((APP_DIR / 'templates/experiments.html').read_text(), 'html.parser')
        completed_card = str(dashboard.select('.dashboard-metrics article')[1])
        stored_card = str(evaluations.select('.evaluation-summary-grid article')[3])
        for language in ('en', 'es'):
            with app.test_request_context('/'), patch('main.get_settings', return_value={}):
                session['language'] = language
                completed = BeautifulSoup(render_template_string(completed_card,
                    pages={'pages': 22, 'axe_issues': 5}), 'html.parser')
                stored = BeautifulSoup(render_template_string(stored_card,
                    summary={'processed_urls': 24}), 'html.parser')
            self.assertEqual(completed.select_one('strong').text, '22')
            self.assertEqual(stored.select_one('strong').text, '24')
            self.assertIn('Resultados de página completados' if language == 'es'
                          else 'Completed page results', completed.text)
            self.assertIn('Resultados de página guardados' if language == 'es'
                          else 'Stored page results', stored.text)
            self.assertIn('no son URLs únicas' if language == 'es'
                          else 'not unique URLs', completed.text)
            self.assertIn('intentos fallidos' if language == 'es'
                          else 'failed attempts', stored.text)
            for text in (completed.text, stored.text):
                self.assertIn('importados' if language == 'es' else 'imported', text)
                self.assertIn('combinados' if language == 'es' else 'combined', text)

    def test_manage_urls_pagination_loading_and_description_use_unique_completed_urls(self):
        for language in ('en', 'es'):
            with app.test_request_context('/urls/manage'), patch('main.get_settings', return_value={}):
                session['language'] = language
                html = render_template('manage_urls.html', category_model=None,
                    category_job={}, uncategorized_count=0, site_categories=[], luna_available=False)
            dom = BeautifulSoup(html, 'html.parser')
            config = json.loads(dom.select_one('#managedUrlConfig').string)
            self.assertEqual(config['rows'], 'URLs únicas' if language == 'es' else 'unique URLs')
            self.assertEqual(config['matches'], 'URLs únicas coincidentes' if language == 'es'
                             else 'matching unique URLs')
            self.assertIn('URLs únicas' if language == 'es' else 'unique URLs', config['loading'])
            heading = dom.select_one('.app-page-heading').text
            self.assertIn('más reciente' if language == 'es' else 'latest completed result', heading)

    def test_summary_keeps_failed_and_imported_records_without_deduplication(self):
        summary = build_experiments_summary([
            {'status': 'completed', 'processed_urls': 10, 'completed_urls': 8},
            {'status': 'completed', 'processed_urls': 5, 'completed_urls': 5,
             'experiment_origin': 'import'},
            {'status': 'running', 'processed_urls': 2, 'completed_urls': 1},
        ])
        self.assertEqual(summary['processed_urls'], 17)
        self.assertEqual(summary['total_experiments'], 3)


if __name__ == '__main__':
    unittest.main()
