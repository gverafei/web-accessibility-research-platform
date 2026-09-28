import json
import tempfile
import unittest
from pathlib import Path

from remediation_taxonomy import axe_taxonomy, category_for_rule


class RemediationTaxonomyTests(unittest.TestCase):
    def test_published_rule_categories(self):
        self.assertEqual(category_for_rule("image-alt"), "Syntactic")
        self.assertEqual(category_for_rule("color-contrast"), "Layout")
        self.assertEqual(category_for_rule("future-rule"), "Unclassified")

    def test_counts_affected_elements(self):
        payload = {"violations": [
            {"id": "image-alt", "impact": "critical", "nodes": [{}, {}]},
            {"id": "color-contrast", "impact": "serious", "nodes": [{}]},
        ]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "axe.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = axe_taxonomy(path)
        self.assertEqual(result["Syntactic"]["count"], 2)
        self.assertEqual(result["Layout"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
