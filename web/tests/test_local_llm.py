import unittest
from unittest.mock import MagicMock, patch

import requests
import json
from local_llm import local_configuration
from remediation_model_choices import model_choices, model_choice


SETTINGS = {'ollama_base_url': 'http://host.docker.internal:11434',
            'ollama_model': 'llama3.1:8b', 'ollama_capabilities_json': '["completion"]'}


def native_response(content, incoming=0, outgoing=0):
    response = MagicMock(status_code=200)
    response.iter_lines.return_value = [
        json.dumps({'message': {'content': content}, 'done': False}).encode(),
        json.dumps({'message': {'content': ''}, 'done': True,
                    'prompt_eval_count': incoming, 'eval_count': outgoing}).encode(),
    ]
    return response


class LocalLlmTests(unittest.TestCase):
    def test_optional_local_choice_preserves_remote_order(self):
        self.assertIsNone(local_configuration({}))
        choices = model_choices(SETTINGS)
        self.assertEqual(choices[0]['id'], 'ollama/llama3.1:8b')
        self.assertEqual(choices[0]['tier'], 'local')
        self.assertEqual(choices[1:], model_choices())
        self.assertFalse(choices[0]['vision'])
        self.assertTrue(model_choices(dict(SETTINGS, ollama_capabilities_json='["completion", "vision"]'))[0]['vision'])
        with self.assertRaises(ValueError):
            model_choice('ollama/other:8b', SETTINGS)

    def test_configuration_validation(self):
        self.assertEqual(local_configuration(SETTINGS)['base_url'], 'http://host.docker.internal:11434/v1')
        self.assertEqual(local_configuration(dict(SETTINGS, ollama_base_url='http://server:11434/v1/'))['base_url'], 'http://server:11434/v1')
        for change in ({'ollama_model': ''}, {'ollama_base_url': ''},
                       {'ollama_base_url': 'file:///tmp/test'},
                       {'ollama_base_url': 'https://user:password@server'},
                       {'ollama_base_url': 'https://ollama.com'},
                       {'ollama_model': 'model-cloud'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                local_configuration(dict(SETTINGS, **change))

    def test_local_dispatch_keeps_parameters_and_has_no_paid_auth(self):
        from remediation_jobs import call_model
        response = native_response('{"patches":[]}', 10, 20)
        messages = [{'role': 'user', 'content': [{'type': 'text', 'text': 'Repair'},
                                                {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,AAAA'}}]}]
        with patch('remediation_jobs.requests.post', return_value=response) as post:
            result = call_model(SETTINGS, 'ollama/llama3.1:8b', 'Repair',
                                json_mode=True, temperature=.5, messages=messages,
                                output_token_limit=6000, reasoning_override='low')
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.args[0], 'http://host.docker.internal:11434/api/chat')
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['model'], 'llama3.1:8b')
        self.assertEqual(payload['options']['temperature'], .5)
        self.assertEqual(payload['options']['num_predict'], 6000)
        self.assertEqual(payload['options']['num_ctx'], 32768)
        self.assertFalse(payload['truncate'])
        self.assertFalse(payload['shift'])
        self.assertEqual(payload['format'], 'json')
        self.assertEqual(payload['messages'][0]['content'], 'Repair')
        self.assertNotIn('reasoning', payload)
        self.assertNotIn('headers', post.call_args.kwargs)
        self.assertEqual(result[1:4], (10, 20, 0.))
        self.assertEqual(result[-1], 'ollama/llama3.1:8b')

    def test_snapshot_survives_settings_changes(self):
        from remediation_jobs import call_model
        response = native_response('HTML')
        with patch('remediation_jobs.requests.post', return_value=response) as post:
            call_model({'_local_llm_config': local_configuration(SETTINGS)},
                       'ollama/llama3.1:8b', 'Generate')
        self.assertIn('host.docker.internal', post.call_args.args[0])

    def test_network_error_does_not_fall_back(self):
        from remediation_jobs import call_model
        with patch('remediation_jobs.requests.post', side_effect=requests.ConnectionError('offline')) as post:
            with self.assertRaises(requests.ConnectionError):
                call_model(SETTINGS, 'ollama/llama3.1:8b', 'Generate')
        self.assertEqual(post.call_count, 1)

    def test_native_vision_and_frozen_context_preserve_complete_messages(self):
        from local_llm import local_chat
        config = dict(local_configuration(SETTINGS), vision=True, context_length=40960)
        response = native_response('ok', 21000, 12)
        messages = [{'role': 'user', 'content': [
            {'type': 'text', 'text': 'complete source'},
            {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,AAAA'}}]}]
        with patch('local_llm.requests.post', return_value=response) as post:
            self.assertEqual(local_chat(config, messages, temperature=.2), ('ok', 21000, 12))
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['messages'][0], {'role': 'user', 'content': 'complete source', 'images': ['AAAA']})
        self.assertEqual(payload['options']['num_ctx'], 40960)
        self.assertEqual(payload['options']['temperature'], .2)

    def test_native_context_overflow_is_explicit_not_silently_retried(self):
        from local_llm import local_chat
        response = MagicMock(status_code=400)
        response.json.return_value = {'error': 'input exceeds context length'}
        with patch('local_llm.requests.post', return_value=response) as post:
            with self.assertRaisesRegex(requests.RequestException, 'input exceeds context length'):
                local_chat(local_configuration(SETTINGS), [{'role': 'user', 'content': 'source'}])
        self.assertEqual(post.call_count, 1)
        from local_llm import LocalModelError
        from remediation_completion import retain_interrupted_result
        self.assertTrue(retain_interrupted_result(42, 'automated', isinstance(LocalModelError('context overflow'), requests.RequestException)))

    def test_non_thinking_mode_and_output_ceiling_are_preserved(self):
        from remediation_jobs import call_model
        settings = dict(SETTINGS, ollama_model='qwen3.5:4b', ollama_capabilities_json='["completion", "thinking"]')
        response = native_response('ok')
        with patch('local_llm.requests.post', return_value=response) as post, \
             patch.dict('os.environ', {'REMEDIATION_OUTPUT_TOKEN_LIMIT': '5000'}):
            call_model(settings, 'ollama/qwen3.5:4b', 'repair', output_token_limit=6000, temperature=.5)
        payload = post.call_args.kwargs['json']
        self.assertFalse(payload['think'])
        self.assertEqual(payload['options']['num_predict'], 5000)
        self.assertEqual(payload['options']['temperature'], .5)

    def test_every_thinking_local_model_uses_bounded_non_thinking_mode(self):
        from local_llm import local_configuration
        settings = dict(SETTINGS, ollama_model='gemma4:latest',
                        ollama_capabilities_json='["completion", "vision", "thinking"]')
        self.assertEqual(local_configuration(settings)['reasoning_effort'], 'none')

    def test_partial_stream_is_never_used_as_a_candidate(self):
        from local_llm import local_chat
        response = native_response('partial HTML')
        response.iter_lines.return_value = [b'{"message":{"content":"partial HTML"},"done":false}']
        with patch('local_llm.requests.post', return_value=response):
            with self.assertRaisesRegex(requests.RequestException, 'partial output was not applied'):
                local_chat(local_configuration(SETTINGS), [{'role': 'user', 'content': 'source'}])
        response.close.assert_called_once()

    def test_local_snapshot_blocks_every_remote_call(self):
        from remediation_jobs import call_model
        with patch('remediation_jobs.requests.post') as post, self.assertRaises(ValueError):
            call_model({'_local_llm_config': local_configuration(SETTINGS)},
                       'openrouter/auto', 'Inspect')
        post.assert_not_called()

    def test_connection_check_only_lists_installed_models(self):
        from main import app
        response = MagicMock()
        response.json.return_value = {'data': [{'id': 'llama3.1:8b'}]}
        with patch('routes.experiments.get_settings', return_value=SETTINGS), \
             patch('routes.experiments.requests.get', return_value=response) as get, \
             patch('routes.experiments.requests.post') as post:
            result = app.test_client().post('/configuration/test-ollama')
        self.assertEqual(result.status_code, 302)
        self.assertEqual(get.call_args.args[0], 'http://host.docker.internal:11434/v1/models')
        self.assertEqual(post.call_count, 1)
        self.assertTrue(post.call_args.args[0].endswith('/api/show'))

    def test_connection_check_handles_ollama_null_model_list(self):
        from main import app
        response = MagicMock()
        response.json.return_value = {'data': None}
        with patch('routes.experiments.get_settings', return_value=SETTINGS), \
             patch('routes.experiments.requests.get', return_value=response):
            result = app.test_client().post('/configuration/test-ollama')
        self.assertEqual(result.status_code, 302)

    def test_form_offers_local_model_without_openrouter(self):
        from flask import render_template
        from main import app
        from remediation_recipes import COMMON_CONDITIONS
        with app.test_request_context('/remediation/new'):
            html = render_template('remediation_runs.html', sources=[], llms=[],
                model_choices=model_choices(SETTINGS), expert_models={},
                wave_available=False, wave_credits_per_iteration=2,
                rag={'available': False}, common_conditions=COMMON_CONDITIONS)
        from bs4 import BeautifulSoup
        dom = BeautifulSoup(html, 'html.parser')
        self.assertIn('ollama/llama3.1:8b', html)
        self.assertEqual(dom.select_one('#modelTierRange')['max'], '8')
        self.assertIn("choice.id==='openai/gpt-6-luna'", html)
        self.assertIn('pr.value=0', html)
        self.assertEqual(dom.select_one('#modelTierRange')['value'], '2')
        self.assertEqual(dom.select_one('#selectedModel')['value'], 'openai/gpt-6-luna')
        self.assertEqual(dom.select_one('#preservationRange')['value'], '0')
        self.assertFalse(dom.select_one('#startRemediationButton').has_attr('disabled'))
        self.assertFalse(dom.select('[name="use_wave"], [name="expert_use_wave"], [name="min_aim"]'))
        self.assertNotIn('f.elements.use_wave', html)
        self.assertIsNone(dom.select_one('[name="use_rag"]'))
        self.assertIsNotNone(dom.select_one('#ragStep'))

    def test_local_selection_is_frozen_in_run(self, act_grounding='on'):
        import json
        act_fields={'act_grounding_configured':'1'}
        if act_grounding is not None:
            act_fields['act_grounding']=act_grounding
        from main import app
        cursor = MagicMock()
        cursor.fetchone.return_value = {'id': 42, 'url': 'https://example.org/', 'normalized_url': 'https://example.org/'}
        cursor.lastrowid = 123
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with patch('routes.remediation.get_connection', return_value=connection), \
             patch('routes.remediation.get_settings', return_value=dict(SETTINGS, app_timezone='UTC', wave_api_key='configured')), \
             patch('routes.remediation.available_llm_options', return_value=[]), \
             patch('routes.remediation.source_snapshot', return_value='<html><body>Source</body></html>'), \
             patch('routes.remediation.classified_page_type', return_value='homepage'):
            response = app.test_client().post('/remediation/new', data={
                'source_result_id': '42', 'selected_model': 'ollama/llama3.1:8b', 'preservation_level': '3',
                **act_fields,
                'use_wave': 'on', 'expert_use_wave': 'on', 'min_aim': '10'})
        self.assertEqual(response.status_code, 302)
        insert = next(call.args[1] for call in cursor.execute.call_args_list if call.args[0].startswith('INSERT INTO remediation_runs'))
        self.assertEqual(insert[5], 'ollama/llama3.1:8b')
        self.assertEqual(insert[7], insert[5])
        self.assertEqual(insert[19], 'local')
        self.assertFalse(insert[17])
        self.assertIsNone(insert[11])
        self.assertIs(insert[-2],act_grounding not in (None,'off'))
        snapshot = next(call.args[1] for call in cursor.execute.call_args_list if 'SET local_llm_config_json=' in call.args[0])
        self.assertEqual(json.loads(snapshot[0]), local_configuration(SETTINGS))
        expert_flag=next(call.args[1] for call in cursor.execute.call_args_list if 'SET use_expert_settings=' in call.args[0])
        self.assertEqual(expert_flag,(False,123))

    def test_act_can_be_disabled_for_controlled_comparison(self):
        self.test_local_selection_is_frozen_in_run('off')

    def test_unchecked_act_switch_disables_grounding(self):
        self.test_local_selection_is_frozen_in_run(None)
