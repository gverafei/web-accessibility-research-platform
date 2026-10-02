import json
import unittest
from unittest.mock import MagicMock, patch

from browser_extension_config import extension_catalog, extension_configuration
from routes.extension_api import create_run, request_payload


class ExtensionControlsTests(unittest.TestCase):
    def test_web_and_extension_share_bilingual_intervention_copy(self):
        from flask import Flask
        from flask_babel import Babel, force_locale, gettext
        from pathlib import Path
        from remediation_control_copy import control_copy
        from routes.extension_api import extension_api_bp
        app = Flask(__name__)
        app.config['BABEL_TRANSLATION_DIRECTORIES'] = str(Path(__file__).resolve().parents[1] / 'app/translations')
        Babel(app)
        app.register_blueprint(extension_api_bp)
        with patch('routes.extension_api.get_settings', return_value={}):
            response = app.test_client().get('/api/browser-extension/configuration')
        self.assertEqual(response.status_code, 200)
        for locale in ('en', 'es'):
            with app.app_context(), force_locale(locale):
                self.assertEqual(response.json['ui_copy'][locale], control_copy(gettext))
        copy = response.json['ui_copy']['en']['preservation']
        self.assertEqual(copy[0]['name'], 'Minimal patches')
        self.assertEqual(copy[3]['description'], 'Regenerate from complete HTML, then refine with localized patches.')
        self.assertNotEqual(response.json['ui_copy']['es'], response.json['ui_copy']['en'])
        for item in copy:
            self.assertNotIn('$', item['description'])
            self.assertNotIn('seconds', item['description'])

    def test_configured_targets_are_visible_and_frozen_during_acquisition(self):
        settings = {'remediation_min_lighthouse':'98', 'remediation_max_axe':'0'}
        for approach in extension_catalog(settings)['preservation']:
            self.assertEqual((approach['recipe']['lighthouse'],approach['recipe']['axe']),(98,0))
        config = extension_configuration({'selected_model':'openai/gpt-6-luna'},settings)
        cursor = MagicMock(lastrowid=10)
        create_run(cursor,42,'https://example.org/',config,
                   {'remediation_min_lighthouse':'80','remediation_max_axe':'50'})
        values = cursor.execute.call_args_list[0].args[1]
        self.assertEqual((values[8],values[9]),(98,0))

    def test_legacy_pending_requests_keep_the_original_defaults(self):
        config = {'selected_model':'openai/gpt-6-luna','preservation_level':0,'use_rag':False}
        cursor = MagicMock(lastrowid=10)
        create_run(cursor,42,'https://example.org/',config,
                   {'remediation_min_lighthouse':'80','remediation_max_axe':'50'})
        values = cursor.execute.call_args_list[0].args[1]
        self.assertEqual((values[8],values[9]),(94,3))

    def test_catalog_is_shared_and_acceptance_does_not_change_with_slider(self):
        catalog = extension_catalog({})
        self.assertEqual(len(catalog['models']), 8)
        self.assertEqual(catalog['default_model'], 'openai/gpt-6-luna')
        for approach in catalog['preservation']:
            self.assertEqual(approach['recipe']['axe'], 3)
            self.assertEqual(approach['recipe']['lighthouse'], 94)
        self.assertEqual(catalog['preservation'][4]['name'], 'Markdown regeneration')

    def test_preservation_colors_match_web_slider(self):
        from pathlib import Path
        catalog = extension_catalog({})
        colors = [approach['color'] for approach in catalog['preservation']]
        self.assertEqual(colors, ['#2f9e66', '#2686c9', '#6558c8', '#9b4fc2', '#c3486b'])
        template = (Path(__file__).resolve().parents[1] / 'app/templates/_remediation_identity.html').read_text()
        for approach in catalog['preservation']:
            self.assertIn(f"{approach['priority']}:'{approach['color']}'", template)

    def test_legacy_numeric_model_does_not_silently_select_another_model(self):
        with self.assertRaises(ValueError):
            extension_configuration({'model_level': 2}, {})

    def test_explicit_local_model_is_unavailable_without_configuration(self):
        with self.assertRaises(ValueError):
            extension_configuration({'selected_model': 'ollama/gemma4:latest'}, {})

    def test_high_reasoning_choice_is_preserved(self):
        config = extension_configuration({'selected_model': 'openai/gpt-6-luna@high'}, {})
        self.assertEqual(config['selected_model'], 'openai/gpt-6-luna@high')
        cursor = MagicMock(lastrowid=10)
        create_run(cursor, 42, 'https://example.org/', config, {})
        values = cursor.execute.call_args_list[0].args[1]
        self.assertEqual(values[4], 'openai/gpt-6-luna')
        self.assertEqual(values[17], 'xhigh')
        self.assertEqual(json.loads(values[18]), ['openai/gpt-6-luna'])
        self.assertEqual(cursor.execute.call_args_list[0].args[0].count('%s'), len(values))

    def test_regeneration_has_execution_mode_and_reference(self):
        config = extension_configuration({'selected_model': 'openai/gpt-6.1-sol', 'preservation_level': 3}, {})
        cursor = MagicMock(lastrowid=10)
        create_run(cursor, 42, 'https://example.org/', config, {})
        values = cursor.execute.call_args_list[0].args[1]
        self.assertEqual(values[14], 'vera_reference')
        self.assertEqual(cursor.execute.call_args_list[2].args[1], ('regenerate_refine', 10))

    def test_invalid_slider_level_is_rejected(self):
        with self.assertRaises(ValueError):
            extension_configuration({'selected_model': 'openai/gpt-6.1-sol', 'preservation_level': 6}, {})

    def test_delayed_local_request_keeps_its_original_endpoint(self):
        frozen = {'endpoint': 'http://original:11434', 'model': 'gemma4:latest', 'vision': False}
        choice = {'id': 'ollama/gemma4:latest', 'model': 'ollama/gemma4:latest', 'tier': 'low'}
        with patch('browser_extension_config.model_choice', return_value=choice), \
             patch('local_llm.local_configuration', return_value=frozen):
            config = extension_configuration({'selected_model': choice['id']}, {})
        cursor = MagicMock(lastrowid=10)
        with patch('local_llm.local_configuration', side_effect=AssertionError('Must not read a changed endpoint')):
            create_run(cursor, 42, 'https://example.org/', config, {})
        self.assertEqual(json.loads(cursor.execute.call_args_list[-1].args[1][0]), frozen)

    def test_delayed_acquisition_uses_saved_choice(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {'status': 'completed'}, {'id': 42},
            {'id': 10, 'status': 'queued', 'accepted_iteration_id': None}]
        config = {'selected_model': 'openai/gpt-6-luna@high', 'preservation_level': 2, 'use_rag': True}
        config = extension_configuration(config, {})
        with patch('routes.extension_api.get_settings', return_value={}), \
             patch('routes.extension_api.create_run', return_value=10) as create:
            request_payload(cursor, {'id': 1, 'url': 'https://example.org/',
                'acquisition_experiment_id': 2, 'configuration_json': json.dumps(config)})
        self.assertEqual(create.call_args.args[3]['selected_model'], config['selected_model'])
