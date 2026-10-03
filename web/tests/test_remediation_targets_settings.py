import unittest
from unittest.mock import MagicMock, patch

from main import app
from settings import SETTING_DEFAULTS


class RemediationTargetSettingsTests(unittest.TestCase):
    def test_web_submission_freezes_server_limits_not_stale_hidden_fields(self):
        settings = {**SETTING_DEFAULTS, 'remediation_max_iterations':'5',
                    'remediation_max_cost_usd':'0.07',
                    'remediation_max_execution_seconds':'410'}
        for level, mode, iterations in ((0,'iterative',5),(3,'iterative',5),
                                        (0,'single_shot',1),(3,'regenerate_only',1)):
            connection = MagicMock()
            cursor = connection.cursor.return_value
            cursor.fetchone.return_value = {'id':42,'url':'https://example.org/'}
            cursor.lastrowid = 10
            with self.subTest(level=level,mode=mode), \
                 patch('routes.remediation.get_settings',return_value=settings), \
                 patch('routes.remediation.available_llm_options',return_value=[]), \
                 patch('routes.remediation.get_connection',return_value=connection), \
                 patch('routes.remediation.source_snapshot',return_value='/mock/source.html'), \
                 patch('routes.remediation.classified_page_type',return_value='general'):
                response=app.test_client().post('/remediation/new',data={
                    'source_result_id':'42','selected_model':'openai/gpt-6-luna',
                    'preservation_level':str(level),'execution_mode':mode,
                    'max_iterations':'3','max_cost_usd':'0.15','max_execution_seconds':'240'})
                self.assertEqual(response.status_code,302)
                inserts=[call for call in cursor.execute.call_args_list
                         if 'INSERT INTO remediation_runs' in call.args[0]]
                self.assertEqual(len(inserts),1)
                values=inserts[0].args[1]
                self.assertEqual((values[8],values[24],values[25]),(iterations,0.07,410))
                connection.commit.assert_called_once()

    def test_invalid_targets_do_not_save_any_configuration(self):
        for values in ({'remediation_min_lighthouse':'101'},
                       {'remediation_max_axe':'-1'},
                       {'remediation_min_lighthouse':'94.5'},
                       {'remediation_max_iterations':'0'},
                       {'remediation_max_iterations':'11'},
                       {'remediation_max_cost_usd':'NaN'},
                       {'remediation_max_cost_usd':'Infinity'},
                       {'remediation_max_cost_usd':'0'},
                       {'remediation_max_execution_seconds':'29'},
                       {'remediation_max_execution_seconds':'7201'}):
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

    def test_configuration_saves_per_run_limits(self):
        for limits in ({'remediation_max_iterations':'5', 'remediation_max_cost_usd':'0.07',
                        'remediation_max_execution_seconds':'410'},
                       {'remediation_max_iterations':'3', 'remediation_max_cost_usd':'0.25',
                        'remediation_max_execution_seconds':'360'}):
            with self.subTest(limits=limits), \
                 patch('routes.experiments.get_settings',return_value=dict(SETTING_DEFAULTS)), \
                 patch('routes.experiments.save_settings') as save:
                response=app.test_client().post('/configuration',data=limits)
                self.assertEqual(response.status_code,302)
                for key, value in limits.items():
                    self.assertEqual(save.call_args.args[0][key], value)

    def test_fresh_installation_preserves_illustrative_study_defaults(self):
        self.assertEqual(SETTING_DEFAULTS['remediation_min_lighthouse'],'94')
        self.assertEqual(SETTING_DEFAULTS['remediation_max_axe'],'3')
        self.assertEqual(SETTING_DEFAULTS['remediation_max_iterations'],'3')
        self.assertEqual(SETTING_DEFAULTS['remediation_max_cost_usd'],'0.25')
        self.assertEqual(SETTING_DEFAULTS['remediation_max_execution_seconds'],'360')
