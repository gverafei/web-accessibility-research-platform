import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup
from flask import render_template

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
if 'database' not in sys.modules:
    stub = types.ModuleType('database')
    stub.init_db = lambda: None
    stub.get_connection = lambda: None
    sys.modules['database'] = stub

from main import app
from navigation import breadcrumbs


class NavigationTests(unittest.TestCase):
    def test_help_footer_uses_canonical_docs_url_in_both_languages(self):
        from flask import session
        root = Path(__file__).resolve().parents[2]
        self.assertIn('site_url: ' + app.config['DOCUMENTATION_URL'],
                      (root / 'mkdocs.yml').read_text())
        for language, label in [('en', 'Help and documentation'),
                                ('es', 'Ayuda y documentación')]:
            with self.subTest(language=language), app.test_request_context('/'), \
                    patch('main.get_settings', return_value={}):
                session['language'] = language
                page = BeautifulSoup(render_template('base.html'), 'html.parser')
                help_link = page.select_one('footer.app-footer a')
                self.assertEqual(help_link['href'], app.config['DOCUMENTATION_URL'])
                self.assertEqual(help_link.get_text(strip=True), label)
                self.assertEqual(help_link['target'], '_blank')
                self.assertIn('noopener', help_link['rel'])
                self.assertIn('noreferrer', help_link['rel'])
                self.assertIsNotNone(help_link.select_one('svg[aria-hidden="true"]'))
                self.assertIsNone(page.select_one('a[href="/about"]'))

    def test_old_about_bookmark_redirects_without_rendering_or_database(self):
        with patch('database.get_connection') as db:
            response = app.test_client().get('/about')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], app.config['DOCUMENTATION_URL'])
        self.assertFalse((Path(__file__).resolve().parents[1] / 'app/templates/about.html').exists())
        db.assert_not_called()

    def test_all_application_locations_use_shared_trail_without_database_queries(self):
        cases = {
            '/': ['Dashboard'], '/acquisition/new': ['New acquisition'],
            '/configuration': ['Configuration'],
            '/evaluations': ['Evaluations'], '/urls/manage': ['Manage URLs'],
            '/experiments/compose': ['Combine evaluations'], '/experiments/import': ['Import'],
            '/comparisons': ['Comparisons'], '/comparisons/17': ['Comparisons', 'Comparison #17'],
            '/remediation/': ['Remediation runs'], '/remediation/new': ['New remediation'],
            '/remediation/templates': ['Templates'],
            '/remediation/788': ['Remediation runs', 'Remediation #788'],
            '/experiments/131': ['Evaluations', 'Evaluation #131'],
            '/experiments/131/loading': ['Evaluations', 'Evaluation #131'],
            '/experiments/131/urls': ['Evaluations', 'Evaluation #131', 'Manage URLs'],
            '/rag-act': ['RAG-ACT'],
            '/rag-act/examples/00000000-0000-4000-8000-000000000001': ['RAG-ACT', 'Example'],
        }
        for path, labels in cases.items():
            with self.subTest(path=path), app.test_request_context(path), \
                    patch('main.get_settings', return_value={}), patch('database.get_connection') as db:
                self.assertEqual([c['label'] for c in breadcrumbs()], labels)
                page = BeautifulSoup(render_template('base.html'), 'html.parser')
                trail = page.select_one('main > nav.app-breadcrumbs')
                self.assertIsNotNone(trail)
                self.assertEqual(trail.select_one('a[aria-label="Home"]')['href'], '/')
                self.assertIsNotNone(trail.select_one('a[aria-label="Home"] svg[aria-hidden="true"]'))
                self.assertEqual(len(trail.select('[aria-current="page"]')), 1)
                self.assertEqual(trail.select_one('[aria-current="page"]').get_text(), labels[-1])
                db.assert_not_called()

    def test_parents_are_real_routes_loading_is_same_depth_and_filters_survive(self):
        cases = {
            '/experiments/131/urls': ['/evaluations', '/experiments/131/loading'],
            '/remediation/788': ['/remediation/'],
            '/comparisons/17': ['/comparisons'],
            '/rag-act/examples/00000000-0000-4000-8000-000000000001?q=image&page=3&size=10':
                ['/rag-act?q=image&size=10&page=3'],
        }
        for path, expected in cases.items():
            with self.subTest(path=path), app.test_request_context(path):
                self.assertEqual([c['url'] for c in breadcrumbs() if 'url' in c], expected)

    def test_spanish_trail_and_sidebar_rag_highlight(self):
        with app.test_request_context('/rag-act'), patch('main.get_settings', return_value={}):
            from flask import session
            session['language'] = 'es'
            page = BeautifulSoup(render_template('base.html'), 'html.parser')
            self.assertIsNotNone(page.select_one('.app-breadcrumbs[aria-label="Ruta de navegación"]'))
            self.assertIn('active', page.select_one('.sidebar-link[aria-label="RAG-ACT"]')['class'])
            configuration = page.select_one('.sidebar-link[href="/configuration"]')
            self.assertNotIn('active', configuration['class'])


if __name__ == '__main__':
    unittest.main()
