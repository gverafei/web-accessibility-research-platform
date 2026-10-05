"""Keep common researcher instructions aligned with deterministic defaults."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'web/app'))
from remediation_recipes import automatic_recipe, COMMON_CONDITIONS


class DocumentationContractsTests(unittest.TestCase):
    def test_recipe_table_only_varies_temperature_not_money_or_time(self):
        text = (ROOT / 'docs/site/guide/remediation.md').read_text()
        self.assertIn(f"US${COMMON_CONDITIONS['cost']}", text)
        self.assertIn(f"{COMMON_CONDITIONS['seconds']} seconds per run", text)
        rows = re.findall(r'^\| ([1-5]) \| [^|]+ \| ([0-9.]+) \|$', text, re.M)
        self.assertEqual(len(rows), 5)
        for (level, temperature), priority in zip(rows, (15, 35, 55, 75, 90)):
            recipe = automatic_recipe(priority)
            self.assertEqual(float(temperature), recipe['temperature'])
            self.assertEqual(recipe['cost'], COMMON_CONDITIONS['cost'])
            self.assertEqual(recipe['seconds'], COMMON_CONDITIONS['seconds'])
        self.assertNotIn('Cost continuation threshold | Time continuation threshold', text)

    def test_rag_links_and_case_outcome_explanation_are_present(self):
        text = (ROOT / 'docs/site/guide/rag.md').read_text()
        for url in ('https://www.w3.org/TR/WCAG22/',
                    'https://www.w3.org/WAI/WCAG22/Understanding/',
                    'https://www.w3.org/WAI/standards-guidelines/act/rules/'):
            self.assertIn(url, text)
        self.assertIn('**test-case outcomes**', text)
        self.assertIn('`embed()`', text)

    def test_upload_limit_is_consistent_across_researcher_guides(self):
        # Config's default is also exercised by test_acquisition_capacity.
        for path in ('guide/acquisition.md', 'guide/local-html.md', 'technical/settings.md'):
            with self.subTest(path=path):
                text = (ROOT / 'docs/site' / path).read_text()
                self.assertIn('3,221,225,472', text)
                self.assertNotIn('1,610,612,736', text)

    def test_exchange_explains_product_not_paper_example_packages(self):
        text = (ROOT / 'docs/site/guide/exchange.md').read_text()
        for phrase in ('**Export data**', '**Remediation runs**', '**Export selected**',
                       'remediation.json', '**Import**', 'historical', 'do **not** queue a job'):
            self.assertIn(phrase, text)
        for path in ('guide/exchange.md', 'guide/remediation.md'):
            guide = (ROOT / 'docs/site' / path).read_text()
            self.assertNotIn('examples/softwarex', guide)
            self.assertNotIn('example-2-remediations-125.warp', guide)


if __name__ == '__main__':
    unittest.main()
