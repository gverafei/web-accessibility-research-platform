"""Categories are observation metadata, not a Tranco-only measurement."""
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import render_template, render_template_string, session

APP_DIR = Path(__file__).resolve().parents[1] / 'app'
sys.path.insert(0, str(APP_DIR))
if 'database' not in sys.modules:
    stub = types.ModuleType('database')
    stub.init_db = lambda: None
    stub.get_connection = lambda: None
    sys.modules['database'] = stub

from main import app
from routes.experiments import build_experiment_analysis


class ReportCategoryTests(unittest.TestCase):
    def test_category_column_is_present_without_tranco_rank_columns(self):
        template = (APP_DIR / 'templates/report.html').read_text()
        columns = template.split('const extraColumns=', 1)[1].split(';extraColumns.', 1)[0]
        for language in ('en', 'es'):
            for source_type in ('url', 'html', 'imported', 'composed', 'tranco'):
                with self.subTest(language=language, source_type=source_type), \
                        app.test_request_context('/'), patch('main.get_settings', return_value={}):
                    session['language'] = language
                    rendered = render_template_string(columns,
                        tranco_sample={'list_id': 'test'} if source_type == 'tranco' else None)
                    keys = [column[0] for column in json.loads(rendered)]
                    self.assertEqual(keys.count('site_category'), 1)
                    labels = dict((column[0], column[1]) for column in json.loads(rendered))
                    self.assertEqual(labels['site_category'],
                                     'Categoría' if language == 'es' else 'Category')
                    self.assertEqual('tranco_rank' in keys, source_type == 'tranco')
                    self.assertEqual('tranco_stratum' in keys, source_type == 'tranco')

    def test_analysis_preserves_categories_and_unclassified_without_ranking(self):
        for language in ('en', 'es'):
            rows = [{'id': 1, 'url': 'https://classified.test/', 'status': 'completed',
                     'site_category': 'Technology', 'axe_violations': 2},
                    {'id': 2, 'url': 'https://unclassified.test/', 'status': 'completed',
                     'site_category': None, 'axe_violations': 0}]
            with app.test_request_context('/'), patch('main.get_settings', return_value={}):
                session['language'] = language
                extras = build_experiment_analysis(rows)['measurement_extras']
            self.assertEqual(extras[0]['site_category'], 'Technology')
            self.assertEqual(extras[1]['site_category'],
                             'Sin clasificar' if language == 'es' else 'Unclassified')
            self.assertIsNone(extras[0]['tranco_rank'])
            self.assertIsNone(rows[1]['site_category'])

    def test_evidence_metadata_includes_category_and_preserves_provenance(self):
        template = (APP_DIR / 'templates/report.html').read_text()
        self.assertIn("{% include '_evaluation_observation_metadata.html' %}", template)
        for language in ('en', 'es'):
            for category in ('Technology', None, '<script>alert(1)</script>'):
                with app.test_request_context('/'), patch('main.get_settings', return_value={}):
                    session['language'] = language
                    html = render_template('_evaluation_observation_metadata.html', item={
                        'site_category': category, 'evaluated_at': '2026-09-20',
                        'provenance': 'composed', 'source_experiment_id': 133})
                self.assertIn('2026-09-20', html)
                self.assertIn('composed', html)
                self.assertIn('#133', html)
                if category is None:
                    self.assertIn('Sin clasificar' if language == 'es' else 'Unclassified', html)
                elif category == 'Technology':
                    self.assertIn(category, html)
                else:
                    self.assertNotIn('<script>', html)
                    self.assertIn('&lt;script&gt;', html)


if __name__ == '__main__':
    unittest.main()
