import unittest
from unittest.mock import patch
from remediation_jobs import call_model


class ExplicitModelPolicyTests(unittest.TestCase):
    def test_empty_paid_response_retains_usage_before_output_validation(self):
        settings = {'openrouter_base_url':'https://example.org','openrouter_api_key':'test'}
        with patch('remediation_jobs.requests.post') as post:
            post.return_value.json.return_value = {
                'model':'future/coder', 'choices':[{'message':{'content':None}}],
                'usage':{'prompt_tokens':80,'completion_tokens':12,'cost':.003}}
            result = call_model(settings, 'future/coder', 'Task')
        self.assertEqual(result[0], '')
        self.assertEqual(result[1:3], (80, 12))
        self.assertAlmostEqual(result[3], .003)

    def test_automatic_routing_is_rejected_without_a_paid_call(self):
        with patch('remediation_jobs.requests.post') as post:
            with self.assertRaisesRegex(ValueError, 'removed'):
                call_model({'openrouter_base_url':'https://example.org','openrouter_api_key':'test'},
                           'openrouter/auto', 'Task')
        post.assert_not_called()

    def test_frozen_unknown_future_model_and_reasoning_are_sent_unchanged(self):
        settings = {'openrouter_base_url':'https://example.org','openrouter_api_key':'test',
                    '_model_configuration':{'model':'future/gpt-lola-6.1','reasoning_effort':'high','temperature_supported':False}}
        with patch('remediation_jobs.requests.post') as post:
            post.return_value.json.return_value={'model':'future/gpt-lola-6.1',
                'choices':[{'message':{'content':'HTML'}}], 'usage':{'cost':.02}}
            result=call_model(settings, 'future/gpt-lola-6.1', 'Task', temperature=.5)
        payload=post.call_args.kwargs['json']
        self.assertEqual(payload['model'],'future/gpt-lola-6.1')
        self.assertEqual(payload['reasoning']['effort'],'high')
        self.assertNotIn('temperature',payload)
        self.assertNotIn('plugins',payload)
        self.assertAlmostEqual(result[3],.02)

    def test_fixed_reasoning_model_does_not_get_an_invented_effort(self):
        settings = {'openrouter_base_url':'https://example.org','openrouter_api_key':'test',
                    '_model_configuration':{'model':'future/coder','reasoning_effort':None}}
        with patch('remediation_jobs.requests.post') as post:
            post.return_value.json.return_value={'choices':[{'message':{'content':'HTML'}}]}
            call_model(settings, 'future/coder', 'Task', reasoning_override='high')
        self.assertNotIn('reasoning',post.call_args.kwargs['json'])
