import unittest
from unittest.mock import patch

from main import app
from settings import SETTING_DEFAULTS


class RemediationTargetSettingsTests(unittest.TestCase):
    def test_invalid_targets_do_not_save_any_configuration(self):
        for values in ({'remediation_min_lighthouse':'101'},
                       {'remediation_max_axe':'-1'},
                       {'remediation_min_lighthouse':'94.5'}):
            with self.subTest(values=values), \
                 patch('routes.experiments.get_settings',return_value=dict(SETTING_DEFAULTS)), \
                 patch('routes.experiments.save_settings') as save:
                response=app.test_client().post('/configuration',data=values)
                self.assertEqual(response.status_code,302)
                save.assert_not_called()

    def test_configuration_saves_zero_and_custom_targets(self):
        with patch('routes.experiments.get_settings',return_value=dict(SETTING_DEFAULTS)), \
             patch('routes.experiments.save_settings') as save:
            response=app.test_client().post('/configuration',data={
                'remediation_min_lighthouse':'96','remediation_max_axe':'0'})
            self.assertEqual(response.status_code,302)
            values=save.call_args.args[0]
            self.assertEqual(values['remediation_min_lighthouse'],'96')
            self.assertEqual(values['remediation_max_axe'],'0')

    def test_fresh_installation_preserves_illustrative_study_defaults(self):
        self.assertEqual(SETTING_DEFAULTS['remediation_min_lighthouse'],'94')
        self.assertEqual(SETTING_DEFAULTS['remediation_max_axe'],'3')
