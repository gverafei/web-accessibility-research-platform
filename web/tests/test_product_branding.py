"""Public naming must not imply a migration of experiment packages."""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
PRODUCT = "A11yResearch: Web Accessibility Research Platform"


class ProductBrandingTests(unittest.TestCase):
    def test_extension_name_and_action_identify_the_product(self):
        manifest = json.loads((ROOT / "browser_extension/manifest.json").read_text())
        self.assertEqual(manifest["name"], PRODUCT)
        self.assertEqual(manifest["action"]["default_title"],
                         "Open A11yResearch accessibility controls")
        for icon in manifest["icons"].values():
            self.assertTrue((ROOT / "browser_extension" / icon).is_file())

    def test_web_and_extension_headers_use_the_same_name(self):
        for relative in ("web/app/templates/base.html", "browser_extension/sidepanel.html"):
            with self.subTest(template=relative):
                source = (ROOT / relative).read_text()
                self.assertIn(PRODUCT, source)
                self.assertIn(">A11yResearch<span", source)

    def test_exchange_docs_and_input_keep_the_existing_extension(self):
        documentation = (ROOT / "docs/site/guide/exchange.md").read_text()
        self.assertIn("extension remains `.warp`", documentation)
        self.assertIn('assert payload["format"] == "warp-experiment"', documentation)
        self.assertIn('assert payload["version"] == 3', documentation)
        self.assertIn('accept=".warp,application/octet-stream"',
                      (ROOT / "web/app/templates/import.html").read_text())
