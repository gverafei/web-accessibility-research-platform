import unittest

from bs4 import BeautifulSoup
from flask import render_template

from main import app
from settings import SETTING_DEFAULTS


class ConfigurationTabsTests(unittest.TestCase):
    def setUp(self):
        with app.test_request_context('/configuration'):
            html = render_template('configuration.html', settings=dict(SETTING_DEFAULTS),
                                   local_models=[], timezone_groups=[], axe_version='test',
                                   clear_experiments_phrase='DELETE')
        self.page = BeautifulSoup(html, 'html.parser')

    def test_tabs_have_accessible_separate_save_scopes(self):
        for name in ('General', 'Models'):
            tab = self.page.select_one(f'#configuration{name}Tab')
            panel = self.page.select_one(f'#configuration{name}')
            self.assertEqual(tab['role'], 'tab')
            self.assertEqual(tab['aria-controls'], panel['id'])
            self.assertEqual(panel['aria-labelledby'], tab['id'])
        form = self.page.select_one('#generalConfigurationForm')
        self.assertIsNotNone(form.select_one('#remediation_min_lighthouse'))
        self.assertIsNone(form.select_one('#modelCatalogEditor'))
        self.assertIsNotNone(self.page.select_one('#configurationModels #saveModelsButton'))
        self.assertIsNotNone(self.page.select_one('#configurationGeneral #clearExperimentsForm'))

    def test_each_tab_has_its_own_primary_save_button(self):
        general = self.page.select('#configurationGeneral button.btn-primary')
        models = self.page.select('#configurationModels button.btn-primary')
        self.assertEqual(len(general), 1)
        self.assertEqual(len(models), 1)
        self.assertIn('Save configuration', general[0].get_text())
        self.assertEqual(models[0]['id'], 'saveModelsButton')
        self.assertEqual(general[0]['form'], 'generalConfigurationForm')
        self.assertIsNone(general[0].find_parent('form'))
        self.assertLess(str(self.page).index('Save configuration'),
                        str(self.page).index('id="remediationTargets"'))
        self.assertLess(str(self.page).index('id="saveModelsButton"'),
                        str(self.page).index('id="modelCatalogRows"'))
        for button in (general[0], models[0]):
            self.assertIn('justify-content-end', button.parent['class'])
        for identity in ('discoverModelsButton', 'refreshOllamaModels'):
            button = self.page.select_one(f'#{identity}')
            self.assertIn('btn-outline-primary', button['class'])
            self.assertIsNotNone(button.select_one('[aria-hidden="true"]'))

    def test_ollama_connection_button_belongs_to_local_panel(self):
        button = self.page.select_one('#localLlmSettings button[formaction]')
        self.assertIn('Test saved Ollama connection', button.get_text())
        self.assertEqual(button.find_parent('form')['id'], 'generalConfigurationForm')
        self.assertNotIn('The model catalogue has its own save button',
                         self.page.select_one('#configurationGeneral').get_text())

    def test_provider_search_and_close_share_a_compact_control_row(self):
        row = self.page.select_one('#modelProviderPicker .model-provider-search-row')
        self.assertIsNotNone(row)
        self.assertEqual(row.select_one('label[for="providerModelSearch"]').get_text(strip=True),
                         'Search provider models')
        controls = row.select_one('.model-provider-search-controls')
        self.assertIsNotNone(controls.select_one('input#providerModelSearch'))
        self.assertIsNotNone(controls.select_one('button#closeProviderPicker'))
        self.assertNotIn('btn-sm', controls.select_one('button')['class'])


if __name__ == '__main__':
    unittest.main()
