"""All display switches apply to existing evidence, not acquisition metadata."""
import itertools
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from main import app
from settings import SETTING_DEFAULTS
from routes import experiments


SWITCHES = ('axe_include_best_practices', 'show_axe_failed_rules',
            'show_axe_needs_review', 'show_axe_densities')


class ReportDisplaySettingsTests(unittest.TestCase):
    def report(self, flags, historical=False, best_practice=7):
        stored = dict(id=42, title='Frozen example', status='completed', source_type='urls',
                      urls='https://example.org/', include_wave=False, include_semantic=False,
                      axe_standard='wcag22aa', axe_include_best_practices=historical)
        row = dict(id=7, url='https://example.org/', status='completed',
                   axe_violations=21, axe_wcag_violations=14,
                   axe_wcag_critical=0, axe_wcag_serious=14,
                   axe_wcag_moderate=0, axe_wcag_minor=0,
                   axe_wcag_failed_rules=3, axe_wcag_needs_review=18,
                   axe_best_practice_issues=best_practice,
                   lighthouse_score=93, dom_nodes=947, images=2, links=3,
                   execution_seconds=4, created_at='2026-10-05')
        settings = {**SETTING_DEFAULTS, **dict(zip(SWITCHES, flags))}
        conn = MagicMock(); cursor = conn.cursor.return_value
        cursor.fetchone.side_effect = [stored, {'id': 1, 'execution_seconds': None}, {'total': 1}]
        cursor.fetchall.return_value = [row]
        with patch.object(experiments, 'get_connection', return_value=conn), \
             patch.object(experiments, 'get_settings', return_value=settings), \
             patch('main.get_settings', return_value=settings):
            response = app.test_client().get('/experiments/42')
        self.assertEqual(response.status_code, 200)
        conn.commit.assert_not_called()
        self.assertTrue(all(call.args[0].lstrip().startswith('SELECT') for call in cursor.execute.call_args_list))
        self.assertEqual(stored['axe_include_best_practices'], historical)
        self.assertEqual(row['axe_violations'], 21)
        return response.get_data(as_text=True)

    def test_all_switch_combinations_render_independently_of_saved_experiment_flag(self):
        for flags in itertools.product(('false', 'true'), repeat=4):
            with self.subTest(flags=flags):
                html = self.report(flags, historical=flags[0] == 'false')
                self.assertEqual('data-column="axe_best_practice"' in html, flags[0] == 'true')
                self.assertEqual('#measurementTable .column-axe_failed_rules{display:none}' in html, flags[1] == 'false')
                self.assertEqual('#measurementTable .column-axe_needs_review{display:none}' in html, flags[2] == 'false')
                self.assertEqual('#measurementTable .column-axe_density' in html, flags[3] == 'false')
                self.assertEqual('Mean Axe issue density</span>' in html, flags[3] == 'true')
                self.assertIn('data-axe_total="14"', html)
                self.assertIn('data-axe_failed_rules="3"', html)
                self.assertIn('data-axe_needs_review="18"', html)

    def test_best_practice_zero_and_unknown_are_not_conflated(self):
        for value in (0, None):
            with self.subTest(value=value):
                html = self.report(('true',) * 4, best_practice=value)
                self.assertIn('"axe_best_practice": ' + ('null' if value is None else '0'), html)
                self.assertIn('data-axe_total="14"', html)
                self.assertIn('td.textContent=value??"—"', html)

    def test_configuration_persists_all_switch_combinations(self):
        for flags in itertools.product((False, True), repeat=4):
            with self.subTest(flags=flags), \
                 patch.object(experiments, 'get_settings', return_value=dict(SETTING_DEFAULTS)), \
                 patch.object(experiments, 'save_settings') as save:
                data = {key: 'on' for key, enabled in zip(SWITCHES, flags) if enabled}
                response = app.test_client().post('/configuration', data=data)
                self.assertEqual(response.status_code, 302)
                self.assertEqual({key: save.call_args.args[0][key] for key in SWITCHES},
                                 dict(zip(SWITCHES, ('true' if value else 'false' for value in flags))))
