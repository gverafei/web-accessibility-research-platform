import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from remediation_call_evidence import RecordedModelCalls
from remediation_agent_runtime import AgentRuntime


class RecordedCallsTests(unittest.TestCase):
    def test_paid_invalid_answer_is_saved_before_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = AgentRuntime(1, 42, .15, 240)
            runtime.skills_for('generate')
            caller = Mock(return_value=('not JSON', 12, 3, .001, .5, 'explicit/model'))
            recorded = RecordedModelCalls(directory, runtime, caller)
            result = recorded({'openrouter_api_key': 'secret'}, 'explicit/model',
                              'Exact prompt', messages=[{'role': 'user', 'content': 'Exact prompt'}])
            with self.assertRaises(ValueError):
                json.loads(result[0])
            text = (Path(directory) / 'model-call-evidence.json').read_text()
            data = json.loads(text)
            self.assertNotIn('secret', text)
            self.assertEqual(data['calls'][0]['prompt'], 'Exact prompt')
            self.assertEqual(data['calls'][0]['cost_usd'], .001)
            self.assertEqual(data['calls'][0]['response'], 'not JSON')
            self.assertEqual(len(data['calls'][0]['response_sha256']), 64)
            self.assertTrue(data['agentic_runtime']['activated_skills'])
            caller.assert_called_once()

    def test_transport_failure_has_no_fabricated_charge(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = AgentRuntime(1, 42, .15, 240)
            caller = Mock(side_effect=RuntimeError('provider error'))
            recorded = RecordedModelCalls(directory, runtime, caller)
            with self.assertRaisesRegex(RuntimeError, 'provider error'):
                recorded({}, 'explicit/model', 'Task')
            data = json.loads((Path(directory) / 'model-call-evidence.json').read_text())
            self.assertEqual(data['calls'][0]['status'], 'transport_failed')
            self.assertNotIn('cost_usd', data['calls'][0])

    def test_checkpoint_retains_calls_and_real_tool_records(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = AgentRuntime(1, 42, .15, 240)
            caller = Mock(return_value=('', 2, 0, .01, .2, 'explicit/model'))
            recorded = RecordedModelCalls(directory, runtime, caller)
            recorded({}, 'explicit/model', 'First')
            recorded({}, 'explicit/model', 'Second')
            runtime.tools.records.append({'tool': 'apply_constrained_patch', 'status': 'completed'})
            recorded.checkpoint()
            data = json.loads((Path(directory) / 'model-call-evidence.json').read_text())
            self.assertEqual([c['call_number'] for c in data['calls']], [1, 2])
            self.assertEqual(data['agentic_runtime']['tool_invocations'][0]['tool'], 'apply_constrained_patch')
