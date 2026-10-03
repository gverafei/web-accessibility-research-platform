import unittest
from pathlib import Path
from unittest.mock import patch
from bs4 import BeautifulSoup
from flask import render_template
from main import app


class HistoryViewTests(unittest.TestCase):
    def test_evaluations_keep_five_cells_and_labelled_actions_in_one_record(self):
        item = dict(id=8, title='Example study', created_at='2026-10-03',
                    source_type='urls', urls='https://example.org/', status='completed',
                    completed_urls=1, processed_urls=1, failed_urls=0, reused_urls=1,
                    total_cost=0, execution_seconds=3, wave_credits=0)
        summary = dict(total_experiments=1, completed_experiments=1, total_cost=0,
                       wave_experiments=0, wave_credits=0, processed_urls=1)
        with app.test_request_context('/evaluations'), patch('main.get_settings', return_value={}):
            dom = BeautifulSoup(render_template('experiments.html', experiments=[item], summary=summary), 'html.parser')
        table = dom.select_one('.evaluation-history-table')
        self.assertEqual(len(table.select('thead th')), 5)
        group = table.select_one('tbody[data-history-entry]')
        self.assertEqual(len(group.select('tr')), 2)
        self.assertEqual(len(group.select_one('tr').select(':scope > td')), 5)
        self.assertEqual(group.select_one('.history-actions-row td')['colspan'], '5')
        self.assertFalse(group.select('[data-row-open]'))
        for action in group.select('.history-action'):
            self.assertEqual(action.select_one('span').get_text(), action['aria-label'])
            self.assertIsNotNone(action.select_one('svg[aria-hidden="true"]'))
        self.assertIsNotNone(group.select_one('.source-url-icon'))
        self.assertNotIn('↗', group.select_one('.evaluation-source-chip').get_text())
        self.assertEqual(dom.select_one('[data-history-view]')['data-history-view'], 'table')
        self.assertEqual([b.get_text(strip=True) for b in dom.select('[data-history-mode]')], ['Table', 'Cards'])

    def test_controls_are_shared_and_localized_without_different_datasets(self):
        with app.test_request_context('/evaluations'), patch('main.get_settings', return_value={}):
            from flask import session
            session['language'] = 'es'
            dom = BeautifulSoup(render_template('_history_view_toggle.html', history_target='test'), 'html.parser')
        self.assertEqual([b.get_text(strip=True) for b in dom.select('button')], ['Tabla', 'Tarjetas'])
        root = Path(__file__).resolve().parents[1] / 'app'
        for template in ('experiments.html', 'remediation_history.html'):
            source = (root/'templates'/template).read_text()
            self.assertIn('_history_view_toggle.html', source)
            self.assertIn('js/history_views.js', source)
            self.assertNotIn('data-row-open', source)
