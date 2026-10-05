"""Composition cannot replace stored observations, even with an obsolete flag."""
import unittest
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
if 'database' not in sys.modules:
    stub = types.ModuleType('database')
    stub.init_db = lambda: None
    stub.get_connection = lambda: None
    sys.modules['database'] = stub

from main import app
from routes import experiments


class CombineAppendOnlyTests(unittest.TestCase):
    def compose(self, sources, existing):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.return_value = {'id': 42, 'status': 'completed'}
        cursor.fetchall.side_effect = [sources, existing, [{'url': 'https://example.test/'}]]
        with app.test_request_context('/experiments/compose', method='POST', data={
                'target_experiment': '42', 'replace_existing': 'true',
                'result_ids': [str(row['id']) for row in sources]},
                headers={'X-Requested-With': 'XMLHttpRequest'}), \
                patch.object(experiments, 'get_connection', return_value=connection), \
                patch.object(experiments, 'clone_result', return_value=900) as clone, \
                patch.object(experiments.os, 'remove') as remove:
            response = experiments.compose_experiment()
        self.assertEqual(response.status_code, 200)
        connection.commit.assert_called_once()
        connection.rollback.assert_not_called()
        remove.assert_not_called()
        self.assertFalse(any('DELETE' in call.args[0].upper()
                             for call in cursor.execute.call_args_list))
        payload = response.get_json()
        if not payload['added']:
            self.assertFalse(any('UPDATE' in call.args[0].upper()
                                 for call in cursor.execute.call_args_list))
        self.assertNotIn('replaced', payload)
        for row in payload['results']:
            self.assertNotIn('replaced', row)
        return payload, clone

    def test_obsolete_replace_flag_cannot_overwrite_existing_normalized_url(self):
        source = {'id': 1, 'experiment_id': 7, 'url': 'https://example.test/',
                  'status': 'completed', 'axe_wcag_violations': 5}
        payload, clone = self.compose([source], [{'normalized_url': 'https://example.test/'}])
        self.assertEqual(payload['added'], 0)
        self.assertEqual(payload['results'], [])
        clone.assert_not_called()

    def test_new_observation_is_copied_with_provenance_but_duplicate_is_not(self):
        sources = [
            {'id': 1, 'experiment_id': 7, 'url': 'https://example.test/', 'status': 'completed'},
            {'id': 2, 'experiment_id': 8, 'url': 'https://new.test/', 'status': 'completed'},
            {'id': 3, 'experiment_id': 9, 'url': 'https://new.test/', 'status': 'completed'},
        ]
        payload, clone = self.compose(sources, [{'normalized_url': 'https://example.test/'}])
        self.assertEqual(payload['added'], 1)
        clone.assert_called_once()
        self.assertEqual(clone.call_args.args[1:], (sources[1], 42, 'composed'))
        self.assertEqual(payload['results'][0]['source_experiment_id'], 8)
        self.assertEqual(payload['results'][0]['provenance'], 'composed')


if __name__ == '__main__':
    unittest.main()
