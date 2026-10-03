import json
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask
from browser_extension_config import extension_configuration
from browser_extension_results import reusable_request, reusable_run, stored_measurements, completion_configuration
from routes.extension_api import extension_api_bp, request_payload


class ExtensionResultsTests(unittest.TestCase):
    def setUp(self):
        self.config = extension_configuration({'selected_model':'openai/gpt-6-luna'}, {})
        self.cursor = MagicMock()

    def entry(self, **overrides):
        return {'id':3,'remediation_run_id':647,'source_result_id':42,
                'run_status':'completed_with_warnings','output_path':'/datasets/remediations/647/result.html',
                'configuration_json':json.dumps(self.config), **overrides}

    @patch('browser_extension_results.candidate_path', return_value=True)
    def test_equivalent_warning_candidate_is_reused(self, path):
        self.cursor.fetchall.return_value = [self.entry()]
        self.assertEqual(reusable_request(self.cursor, 'https://example.org', 42, self.config)['id'], 3)

    @patch('browser_extension_results.candidate_path', return_value=True)
    def test_url_and_sliders_reuse_even_with_a_newer_acquisition(self, path):
        self.cursor.fetchall.return_value = [self.entry(source_result_id=43)]
        self.assertEqual(reusable_request(self.cursor, 'https://example.org',42,self.config)['id'],3)
        for key, value in [('use_rag', True),('research_targets',{'axe':0,'lighthouse':100})]:
            self.cursor.fetchall.return_value = [self.entry(configuration_json=json.dumps({**self.config,key:value}))]
            self.assertEqual(reusable_request(self.cursor,'https://example.org',42,self.config)['id'],3)

    @patch('browser_extension_results.candidate_path', return_value=True)
    def test_different_model_reasoning_or_intervention_is_not_reused(self, path):
        for config in [
            {**self.config,'preservation_level':2},
            {**self.config,'model_configuration':{**self.config['model_configuration'],'model':'other/model'}},
            {**self.config,'model_configuration':{**self.config['model_configuration'],'reasoning_effort':'high'}},
            {'selected_model':'openai/gpt-6-luna','preservation_level':0},
            [],
        ]:
            self.cursor.fetchall.return_value = [self.entry(configuration_json=json.dumps(config))]
            self.assertIsNone(reusable_request(self.cursor,'https://example.org',42,self.config))

    @patch('browser_extension_results.candidate_path', return_value=True)
    def test_catalogue_presentation_changes_do_not_invalidate_cache(self, path):
        saved={**self.config,'selected_model':'old-catalogue-alias',
               'model_configuration':{**self.config['model_configuration'],'color':'#123456',
                                      'label':'Renamed','digest':'old','input_price':9}}
        self.cursor.fetchall.return_value=[self.entry(configuration_json=json.dumps(saved))]
        self.assertEqual(reusable_request(self.cursor,'https://example.org',42,self.config)['id'],3)

    def backend_run(self, **overrides):
        return {'id':787,'generator_model':self.config['model_configuration']['model'],
                'model_config_json':json.dumps(self.config['model_configuration']),
                'accessibility_priority':15,'execution_mode':'iterative','use_rag':False,
                'max_axe':3,'min_lighthouse':94,'model_cost_tier':'high',
                'status':'accepted','output_path':'/datasets/remediations/787/result.html',**overrides}

    @patch('browser_extension_results.candidate_path', return_value=True)
    def test_web_created_run_is_available_without_extension_request(self, path):
        self.cursor.fetchall.return_value=[self.backend_run()]
        self.assertEqual(reusable_run(self.cursor,'https://example.org',self.config)['id'],787)
        self.assertEqual(self.cursor.execute.call_args.args[1],('https://example.org',))
        for overrides in [{'execution_mode':'single_shot'},{'accessibility_priority':55},
                          {'model_config_json':'{}'},{'generator_model':'other/model'}]:
            self.cursor.fetchall.return_value=[self.backend_run(**overrides)]
            self.assertIsNone(reusable_run(self.cursor,'https://example.org',self.config))
        path.return_value=None
        self.cursor.fetchall.return_value=[self.backend_run()]
        self.assertIsNone(reusable_run(self.cursor,'https://example.org',self.config))
        self.cursor.fetchall.return_value=[self.backend_run(status='running',output_path=None)]
        self.assertEqual(reusable_run(self.cursor,'https://example.org',self.config)['id'],787)

    def test_completion_reports_frozen_rag_not_retrieval_controls(self):
        config=completion_configuration(self.backend_run(use_rag=True))
        self.assertTrue(config['rag'])
        self.assertEqual(config['preservation'],0)
        self.assertEqual(config['preservationName'],'Minimal patches')

    @patch('browser_extension_results.candidate_path', return_value=None)
    def test_missing_output_and_failed_runs_are_not_reused(self, path):
        for item in [self.entry(),self.entry(run_status='failed'),self.entry(configuration_json='bad')]:
            self.cursor.fetchall.return_value = [item]
            self.assertIsNone(reusable_request(self.cursor,'https://example.org',42,self.config))

    def test_existing_active_run_is_followed_without_duplicate(self):
        self.cursor.fetchall.return_value = [self.entry(run_status='running',output_path=None)]
        self.assertEqual(reusable_request(self.cursor,'https://example.org',42,self.config)['id'],3)
        self.cursor.fetchall.return_value = [self.entry(remediation_run_id=None,acquisition_status='running')]
        self.assertEqual(reusable_request(self.cursor,'https://example.org',None,self.config)['id'],3)
        self.assertEqual(reusable_request(self.cursor,'https://example.org',42,self.config)['id'],3)
        self.cursor.fetchall.return_value = [self.entry(remediation_run_id=None,acquisition_status='completed',
            acquisition_experiment_id=12,source_experiment_id=12)]
        self.assertEqual(reusable_request(self.cursor,'https://example.org',42,self.config)['id'],3)
        self.cursor.fetchall.return_value=[self.entry(remediation_run_id=None,
            acquisition_status='completed',status='failed')]
        self.assertIsNone(reusable_request(self.cursor,'https://example.org',42,self.config))

    @patch('routes.extension_api.get_settings', return_value={})
    @patch('routes.extension_api.get_connection')
    def test_submission_lock_timeout_and_error_close_connection(self, connect, settings):
        connect.return_value.cursor.return_value = self.cursor
        self.cursor.fetchone.return_value = {'locked':0}
        response=self.client().post('/api/browser-extension/requests',json={
            'url':'https://example.org','selected_model':'openai/gpt-6-luna'})
        self.assertEqual(response.status_code,409)
        connect.return_value.close.assert_called_once()
        connect.return_value.close.reset_mock()
        self.cursor.execute.side_effect=RuntimeError('Database unavailable')
        client=self.client(); client.application.testing=True
        with self.assertRaises(RuntimeError):
            client.post('/api/browser-extension/requests',json={
                'url':'https://example.org','selected_model':'openai/gpt-6-luna'})
        connect.return_value.close.assert_called_once()

    def test_zero_and_missing_values_are_distinct(self):
        self.cursor.fetchone.side_effect = [{'axe_violations':0,'lighthouse_score':0},{}]
        result = stored_measurements(self.cursor,{'id':647,'source_result_id':42,'max_axe':0,'min_lighthouse':94},9)
        self.assertEqual(result['original'],{'axe':0,'lighthouse':0})
        self.assertEqual(result['final'],{'axe':None,'lighthouse':None})
        self.assertEqual(result['targets']['axe'],0)

    @patch('routes.extension_api.url_for', return_value='http://localhost/report')
    def test_payload_uses_retained_iteration_not_last_attempt(self, url):
        self.cursor.fetchone.side_effect = [
            {'id':647,'status':'completed_with_warnings','accepted_iteration_id':8,
             'source_result_id':42,'max_axe':3,'min_lighthouse':94},
            {'axe_violations':169,'lighthouse_score':88},
            {'axe_violations':37,'lighthouse_score':100}]
        result = request_payload(self.cursor,{'id':3,'remediation_run_id':647})
        self.assertEqual(result['measurements']['iteration_id'],8)
        self.assertEqual(result['measurements']['final'],{'axe':37,'lighthouse':100})
        self.assertEqual(self.cursor.execute.call_args.args[1],(8,647))

    def client(self):
        app = Flask(__name__); app.register_blueprint(extension_api_bp)
        return app.test_client()

    @patch('routes.extension_api.create_run')
    @patch('routes.extension_api.reusable_request')
    @patch('routes.extension_api.get_settings', return_value={})
    @patch('routes.extension_api.get_connection')
    def test_cached_post_does_not_insert_or_create_run(self, connect, settings, reuse, create):
        connection = connect.return_value; connection.cursor.return_value = self.cursor
        self.cursor.fetchone.side_effect = [{'locked':1},{'id':42}]
        reuse.return_value = self.entry()
        response = self.client().post('/api/browser-extension/requests',json={
            'url':'https://example.org','selected_model':'openai/gpt-6-luna'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json['reused']); create.assert_not_called()
        self.assertFalse(any('INSERT' in call.args[0] for call in self.cursor.execute.call_args_list))

    @patch('routes.extension_api.create_run')
    @patch('routes.extension_api.reusable_request')
    @patch('routes.extension_api.get_settings', return_value={})
    @patch('routes.extension_api.get_connection')
    def test_force_rerun_queues_uncached_acquisition(self, connect, settings, reuse, create):
        connect.return_value.cursor.return_value = self.cursor
        self.cursor.fetchone.return_value = {'locked':1}; self.cursor.lastrowid=99
        response = self.client().post('/api/browser-extension/requests',json={
            'url':'https://example.org','selected_model':'openai/gpt-6-luna','force_rerun':True})
        self.assertEqual(response.status_code,202)
        reuse.assert_not_called(); create.assert_not_called()
        insert = next(call for call in self.cursor.execute.call_args_list if 'INSERT INTO experiments' in call.args[0])
        self.assertFalse(insert.args[1][2])
        self.assertEqual(insert.args[0].count('%s'),len(insert.args[1]))

    @patch('routes.extension_api.create_run')
    @patch('routes.extension_api.reusable_run')
    @patch('routes.extension_api.reusable_request',return_value=None)
    @patch('routes.extension_api.get_settings',return_value={})
    @patch('routes.extension_api.get_connection')
    def test_recover_web_run_only_inserts_delivery_binding(self, connect, settings, reuse, saved, create):
        connect.return_value.cursor.return_value=self.cursor
        self.cursor.fetchone.side_effect=[{'locked':1},{'id':42}]
        self.cursor.lastrowid=55
        saved.return_value=self.backend_run()
        response=self.client().post('/api/browser-extension/requests',json={
            'url':'https://example.org','selected_model':'openai/gpt-6-luna','use_rag':True})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['id'],55)
        self.assertTrue(response.json['reused'])
        create.assert_not_called()
        inserts=[call for call in self.cursor.execute.call_args_list if 'INSERT' in call.args[0]]
        self.assertEqual(len(inserts),1)
        self.assertIn('INSERT INTO browser_remediation_requests',inserts[0].args[0])
        self.assertEqual(inserts[0].args[0].count('%s'),len(inserts[0].args[1]))
        self.assertFalse(json.loads(inserts[0].args[1][-1])['use_rag'])

    @patch('routes.extension_api.get_connection')
    def test_non_boolean_rerun_rejected_before_any_database_write(self, connect):
        response = self.client().post('/api/browser-extension/requests',json={
            'url':'https://example.org','force_rerun':'false'})
        self.assertEqual(response.status_code,400); connect.assert_not_called()
