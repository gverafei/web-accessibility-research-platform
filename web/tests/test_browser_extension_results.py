import json
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask
from browser_extension_config import extension_configuration
from browser_extension_results import reusable_request, stored_measurements
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
    def test_changed_source_or_controls_are_not_reused(self, path):
        self.cursor.fetchall.return_value = [self.entry(source_result_id=43)]
        self.assertIsNone(reusable_request(self.cursor, 'https://example.org',42,self.config))
        for key, value in [('use_rag', True),('preservation_level',0),('selected_model','other/model'),
                           ('research_targets',{'axe':0,'lighthouse':100})]:
            self.cursor.fetchall.return_value = [self.entry(configuration_json=json.dumps({**self.config,key:value}))]
            self.assertIsNone(reusable_request(self.cursor,'https://example.org',42,self.config))

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
        self.cursor.fetchall.return_value = [self.entry(remediation_run_id=None,acquisition_status='completed',
            acquisition_experiment_id=12,source_experiment_id=12)]
        self.assertEqual(reusable_request(self.cursor,'https://example.org',42,self.config)['id'],3)

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

    @patch('routes.extension_api.get_connection')
    def test_non_boolean_rerun_rejected_before_any_database_write(self, connect):
        response = self.client().post('/api/browser-extension/requests',json={
            'url':'https://example.org','force_rerun':'false'})
        self.assertEqual(response.status_code,400); connect.assert_not_called()
