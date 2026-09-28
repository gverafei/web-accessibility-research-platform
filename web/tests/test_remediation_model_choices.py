import unittest
import json
from unittest.mock import MagicMock, patch
from remediation_model_choices import model_choices,model_choice


class UserModelChoiceTests(unittest.TestCase):
    def test_models_expose_current_gpt6_recipes(self):
        choices=model_choices()
        self.assertEqual(len(choices),8)
        self.assertTrue(all('reference_cost' not in choice for choice in choices))
        self.assertEqual(choices[0]['id'],'meta-llama/llama-4-maverick')
        self.assertEqual(choices[1]['id'],'qwen/qwen3-coder-plus')
        self.assertEqual(choices[2]['id'],'openai/gpt-6-luna')
        self.assertEqual(choices[4]['id'],'openai/gpt-6-luna@high')
        self.assertEqual(choices[4]['model'],'openai/gpt-6-luna')
        self.assertEqual(choices[4]['tier'],'xhigh')
        self.assertEqual(choices[4]['reasoning_effort'],'high')
        self.assertEqual(choices[5]['id'],'openai/gpt-6-sol')
        self.assertEqual(choices[5]['tier'],'max')
        self.assertEqual(choices[5]['reasoning_effort'],'low')
        self.assertEqual(choices[6]['id'],'openai/gpt-6-astra')
        self.assertEqual(choices[7]['id'],'anthropic/claude-opus-5.5')

    def test_choices_do_not_enable_expensive_reasoning_or_auto_routing(self):
        for choice in model_choices():
            self.assertIn(choice['reasoning_effort'],(None,'low','high'))
            self.assertNotIn('openrouter/auto',choice['id'])
            self.assertNotIn('preview',choice['id'])
        self.assertFalse(model_choice('qwen/qwen3-coder-plus')['vision'])
        self.assertFalse(model_choice('openai/gpt-6-sol')['temperature_supported'])
        with self.assertRaises(ValueError): model_choice('openrouter/auto')


class UserModelRouteTests(unittest.TestCase):
    def submit(self, selected):
        from main import app
        cursor=MagicMock()
        cursor.fetchone.return_value={'id':42,'url':'https://example.org/','normalized_url':'https://example.org/'}
        cursor.lastrowid=123
        connection=MagicMock()
        connection.cursor.return_value=cursor
        with patch('routes.remediation.get_connection',return_value=connection), \
             patch('routes.remediation.get_settings',return_value={'app_timezone':'UTC'}), \
             patch('routes.remediation.available_llm_options',return_value=[]), \
             patch('routes.remediation.source_snapshot',return_value='<html><body>Source</body></html>'), \
             patch('routes.remediation.classified_page_type',return_value='homepage'):
            response=app.test_client().post('/remediation/new',data={
                'source_result_id':'42','selected_model':selected,
                'preservation_level':'3','regeneration_reference':'on'})
        return response,cursor

    def test_selected_sol_is_persisted_without_router_or_other_models(self):
        response,cursor=self.submit('openai/gpt-6-sol')
        self.assertEqual(response.status_code,302)
        inserts=[call.args for call in cursor.execute.call_args_list
                 if call.args[0].startswith('INSERT INTO remediation_runs')]
        self.assertEqual(len(inserts),1)
        values=inserts[0][1]
        self.assertEqual(values[5],'openai/gpt-6-sol')
        self.assertEqual(values[7],'openai/gpt-6-sol')
        self.assertEqual(values[18],'user')
        self.assertEqual(values[19],'max')
        self.assertEqual(json.loads(values[20]),['openai/gpt-6-sol'])
        self.assertEqual(values[14],.5)

    def test_luna_high_selection_persists_api_model_and_recipe(self):
        response,cursor=self.submit('openai/gpt-6-luna@high')
        self.assertEqual(response.status_code,302)
        inserts=[call.args for call in cursor.execute.call_args_list
                 if call.args[0].startswith('INSERT INTO remediation_runs')]
        values=inserts[0][1]
        self.assertEqual(values[5],'openai/gpt-6-luna')
        self.assertEqual(values[19],'xhigh')

    def test_router_cannot_be_submitted_as_slider_model(self):
        response,cursor=self.submit('openrouter/auto')
        self.assertEqual(response.status_code,302)
        self.assertFalse(any(call.args[0].startswith('INSERT INTO remediation_runs')
                             for call in cursor.execute.call_args_list))
