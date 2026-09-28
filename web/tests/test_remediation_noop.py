import unittest
from remediation_completion import measurable_noop


class MeasurableNoopTests(unittest.TestCase):
    def test_valid_empty_plan_can_be_measured(self):
        self.assertTrue(measurable_noop({'applied': [], 'skipped': []}))

    def test_failed_selectors_are_not_noop(self):
        self.assertFalse(measurable_noop({'applied': [], 'skipped': [{'reason': 'selector did not match'}]}))

    def test_missing_or_applied_plan_is_not_noop(self):
        for result in (None, {}, {'applied': []}, {'applied': [{'action': 'set_attribute'}], 'skipped': []}):
            self.assertFalse(measurable_noop(result))
