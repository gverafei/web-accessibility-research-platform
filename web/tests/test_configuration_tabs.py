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

    def test_resource_limits_have_shared_style_labels_bounds_and_defaults(self):
        form = self.page.select_one('#generalConfigurationForm #remediationTargets')
        for key, minimum, maximum, value in (
            ('remediation_max_iterations','1','10','3'),
            ('remediation_max_cost_usd','0.01','100','0.25'),
            ('remediation_max_execution_seconds','30','7200','360'),
        ):
            with self.subTest(key=key):
                control = form.select_one('#'+key)
                self.assertIsNotNone(form.select_one('label[for="'+key+'"]'))
                self.assertEqual(control['name'],key)
                self.assertIn('form-control',control['class'])
                self.assertIn('required',control.attrs)
                self.assertEqual((control['min'],control['max'],control['value']),
                                 (minimum,maximum,value))

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
        for identity, style in (('discoverModelsButton', 'btn-outline-secondary'),
                                ('refreshOllamaModels', 'btn-outline-primary')):
            button = self.page.select_one(f'#{identity}')
            self.assertIn(style, button['class'])
            self.assertIsNotNone(button.select_one('[aria-hidden="true"]'))

    def test_ollama_connection_button_belongs_to_local_panel(self):
        button = self.page.select_one('#localLlmSettings #testOllamaConnection')
        self.assertIn('Test Ollama connection', button.get_text())
        self.assertEqual(button['type'], 'button')
        self.assertEqual(button.find_parent('form')['id'], 'generalConfigurationForm')
        self.assertNotIn('The model catalogue has its own save button',
                         self.page.select_one('#configurationGeneral').get_text())

    def test_rag_maintenance_is_separate_from_saving_settings(self):
        self.assertIsNone(self.page.select_one('#ragKnowledge'))
        self.assertIsNone(self.page.select_one('script[src*="rag_knowledge.js"]'))
        self.assertEqual(self.page.select_one('.sidebar-link[aria-label="RAG-ACT"]')['href'],
                         '/rag-act')

    def test_provider_search_and_close_share_a_compact_control_row(self):
        row = self.page.select_one('#modelProviderPicker .model-provider-search-row')
        self.assertIsNotNone(row)
        self.assertEqual(row.select_one('label[for="providerModelSearch"]').get_text(strip=True),
                         'Search provider models')
        controls = row.select_one('.model-provider-search-controls')
        self.assertIsNotNone(controls.select_one('input#providerModelSearch'))
        self.assertIsNotNone(controls.select_one('button#closeProviderPicker'))
        self.assertNotIn('btn-sm', controls.select_one('button')['class'])

    def test_model_catalogue_has_one_toolbar_without_repeating_the_tab_title(self):
        panel = self.page.select_one('#modelCatalogEditor')
        self.assertIsNone(panel.select_one('h2'))
        toolbar = panel.select_one('.settings-toolbar')
        self.assertIsNotNone(toolbar.select_one('p.settings-toolbar-description'))
        for identity in ('saveModelsButton', 'discoverModelsButton'):
            button = toolbar.select_one('#'+identity)
            self.assertIsNotNone(button)
            self.assertIn('btn-sm', button['class'])

    def test_model_save_feedback_remains_visible_after_the_toolbar(self):
        button = self.page.select_one('#saveModelsButton')
        status = self.page.select_one('#modelCatalogStatus')
        self.assertIs(button.find_parent(class_='card-body'), status.parent)
        self.assertIn('settings-toolbar', status.find_previous_sibling()['class'])
        self.assertEqual(status['role'], 'status')
        self.assertEqual(status['aria-live'], 'polite')


if __name__ == '__main__':
    unittest.main()
