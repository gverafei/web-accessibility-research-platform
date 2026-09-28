import unittest
from unittest.mock import patch,Mock
import tempfile
from bs4 import BeautifulSoup
from born_framework import framework_assets,embed_framework,framework_evidence
from born_content import layout_only


class BornFrameworkTests(unittest.TestCase):
    def test_assets_are_cached_and_not_downloaded_on_each_iteration(self):
        response=Mock(text='/* Bootstrap 5.3.8 */'+('x'*1100))
        with tempfile.TemporaryDirectory() as root,patch('born_framework.requests.get',return_value=response) as get:
            first=framework_assets(root); second=framework_assets(root)
        self.assertEqual(first,second)
        self.assertEqual(get.call_count,2)
        self.assertEqual(framework_evidence(first)['version'],'5.3.8')

    def test_delivered_document_does_not_need_browser_cdn_access(self):
        document='<html><head><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css"></head><body><main><div data-warp-slot="c0">Content</div></main><script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js"></script></body></html>'
        output=embed_framework(document,{'css':'.container{max-width:1200px}','javascript':'/* Bootstrap bundle */'})
        soup=BeautifulSoup(output,'html.parser')
        self.assertFalse(soup.select('link[href],script[src]'))
        self.assertEqual(len(soup.select('[data-warp-framework]')),2)
        self.assertNotIn('max-width:1200px',layout_only(output))
        self.assertIn('data-warp-slot="c0"',layout_only(output))
