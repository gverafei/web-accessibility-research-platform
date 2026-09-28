import unittest
from copy import deepcopy
from remediation_content_contract import grounded_lighthouse_context


class LighthousePatchContextTests(unittest.TestCase):
    def test_missing_nodes_are_not_patch_targets_and_raw_input_is_immutable(self):
        findings = [{'audit': 'button-name', 'items': [{'selector': '#missing'}, {'selector': '#real'}]}]
        original = deepcopy(findings)
        result, omitted = grounded_lighthouse_context(findings, '<button id="real">Go</button>')
        self.assertEqual(result[0]['items'], [{'selector': '#real'}])
        self.assertEqual(omitted[0]['selectors'], ['#missing'])
        self.assertEqual(findings, original)

    def test_fully_unmatched_audit_is_removed_only_from_prompt(self):
        result, omitted = grounded_lighthouse_context([{'audit': 'name', 'items': [{'selector': '#missing'}]}], '<p>Text</p>')
        self.assertEqual(result, [])
        self.assertEqual(len(omitted), 1)

    def test_non_node_and_uninterpretable_selectors_are_not_silently_discarded(self):
        findings = [{'audit': 'language', 'items': []}, {'audit': 'frame', 'items': [{'selector': '[[invalid'}]}]
        result, omitted = grounded_lighthouse_context(findings, '<p>Text</p>')
        self.assertEqual(result, findings)
        self.assertEqual(omitted, [])
