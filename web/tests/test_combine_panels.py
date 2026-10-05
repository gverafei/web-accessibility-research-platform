"""Both composition pickers share the same header and responsive layout."""
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup
from flask import render_template, session

from main import app


class CombinePanelTests(unittest.TestCase):
    def test_picker_headers_precede_page_titles_in_both_languages_and_modes(self):
        target = dict(id=42, title='Stored collection', source_type='urls')
        for language in ('en', 'es'):
            for selected_id in (None, 42):
                with self.subTest(language=language, target=selected_id), \
                        app.test_request_context('/experiments/compose'), \
                        patch('main.get_settings', return_value={}):
                    session['language'] = language
                    dom = BeautifulSoup(render_template(
                        'compose.html', targets=[target], selected_target=target,
                        selected_target_id=selected_id, target_results=[],
                        available_results=[]), 'html.parser')
                for picker_id in ('targetPicker', 'sourceExperiment'):
                    picker = dom.select_one('#' + picker_id)
                    header = picker.find_parent(class_='dataset-target-inline')
                    self.assertIsNotNone(header)
                    self.assertEqual(picker['class'], ['form-select'])
                    self.assertIsNotNone(header.select_one('label[for="' + picker_id + '"]'))
                    pane = header.find_parent('section')
                    self.assertIs(pane.find(recursive=False), header)
                    self.assertIn('dataset-pane-title', header.find_next_sibling()['class'])
                self.assertIsNotNone(dom.select_one('#composeForm #addSelected'))
                self.assertIsNotNone(dom.select_one('#composeForm #sourceExperiment'))
                self.assertIsNone(dom.select_one('.dataset-source-bar'))
                self.assertEqual(len(dom.select('#libraryCount')), 1)
                self.assertEqual(len(dom.select('#currentResultCount')), 1)
                self.assertEqual(bool(dom.select_one('.dataset-report-action')), bool(selected_id))
                toolbars = dom.select('.dataset-list-toolbar')
                self.assertEqual(len(toolbars), 2)
                for toolbar in toolbars:
                    self.assertEqual(len(toolbar.select('.form-check-input')), 1)
                    self.assertEqual(len(toolbar.select('.list-filter-control input')), 1)
                    self.assertIsNotNone(toolbar.select_one('.list-filter-control svg[aria-hidden="true"]'))
                    self.assertIsNotNone(toolbar.select_one('.dataset-selection-count strong'))
                    self.assertFalse(toolbar.select('button'))
                self.assertEqual(toolbars[0].select_one('input[type="search"]')['placeholder'],
                                 toolbars[1].select_one('input[type="search"]')['placeholder'])
                self.assertIsNotNone(dom.select_one('.dataset-pane-footer #removeSelected'))
                self.assertIsNone(dom.select_one('#replace_existing'))
                self.assertNotIn('replace_existing', str(dom))
                if not selected_id:
                    self.assertIsNotNone(dom.select_one('.dataset-pane-footer #title'))
                    self.assertIsNotNone(dom.select_one('.dataset-pane-footer #saveNewDataset'))

    def test_shared_tracks_and_checkbox_alignment_live_in_canonical_theme(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        css = (root / 'web/app/static/css/theme.css').read_text()
        self.assertIn('grid-template-rows: subgrid', css)
        self.assertIn('auto auto auto minmax(0, 1fr) auto', css)
        self.assertIn('.dataset-workspace .form-check-input { float: none; margin: 0;', css)
        self.assertEqual(css, (root / 'browser_extension/theme.css').read_text())


if __name__ == '__main__':
    unittest.main()
