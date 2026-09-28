import unittest
from bs4 import BeautifulSoup
from regeneration_references import EXAMPLES, select_reference
from regeneration_references import ensure_design_base
from vera_regeneration import generation_messages, generation_evidence
from vera_prompt import REFINED_INSTRUCTION


class PageReferencesTests(unittest.TestCase):
    def test_bootstrap_interactive_bundle_enforced_once_only_when_needed(self):
        from regeneration_components import BOOTSTRAP_BUNDLE
        html='<html><head></head><body><button data-bs-toggle="collapse" data-bs-target="#nav">Menu</button><nav id="nav"></nav><script src="https://cdn.test/bootstrap.js"></script></body></html>'
        candidate,evidence=ensure_design_base(html,'bootstrap')
        self.assertIn(BOOTSTRAP_BUNDLE,candidate)
        self.assertNotIn('https://cdn.test/bootstrap.js',candidate)
        self.assertEqual(ensure_design_base(candidate,'bootstrap')[1]['changes'],[])
        self.assertFalse(BeautifulSoup(ensure_design_base('<html><head></head><body>Static</body></html>','bootstrap')[0],'html.parser').find_all('script'))
        duplicated=candidate.replace('</body>',f'<script src="{BOOTSTRAP_BUNDLE}"></script></body>')
        self.assertEqual(len(BeautifulSoup(ensure_design_base(duplicated,'bootstrap')[0],'html.parser').select('script[src]')),1)

    def test_interaction_contract_includes_examples_and_accessibility_limits(self):
        messages=generation_messages('<nav>Links</nav>','https://example.org/',adaptive=True)
        advice=messages[3]['content']
        for term in ('data-bs-toggle="collapse"','aria-controls','bootstrap.bundle.min.js','shown.bs.modal','script-disabled','keyboard'):
            self.assertIn(term,advice)

    def test_bulma_references_and_dependencies_are_not_bootstrap(self):
        from regeneration_references import selected_framework
        self.assertEqual(selected_framework('bulma_reference'),'bulma')
        for kind in ('<h1>Source</h1>','<article>News</article>'*3,'<form><input name="a"><input name="b"></form>'):
            reference=select_reference(kind,'bulma')
            self.assertIn('bulma@1.0.4',reference['html'])
            for old in ('bootstrap','row-cols','card-body','form-control','data-bs-'):
                self.assertNotIn(old,reference['html'])
        reference=select_reference('<article>News</article>'*3,'bulma')
        self.assertIn('card-content',reference['html'])
        self.assertIn('is-12-mobile',reference['html'])
        self.assertNotIn('is-12 ',reference['html'])
        messages=generation_messages('# Content','https://example.org/',adaptive=True,framework='bulma')
        self.assertIn('BULMA 1.0.4 CONTRACT',messages[0]['content'])
        self.assertIn('no built-in JavaScript',messages[3]['content'])
        candidate,_=ensure_design_base('<html><head><link rel="stylesheet" href="https://cdn.test/bootstrap.css"></head><body>Content</body></html>','bulma')
        self.assertIn('bulma@1.0.4',candidate)
        self.assertNotIn('bootstrap.css',candidate)

    def test_design_base_is_enforced_and_idempotent(self):
        source='<!doctype html><html><head><link rel="stylesheet" href="https://cdn.example/bootstrap.css"><style>p{color:black}</style></head><body><main>Original</main></body></html>'
        candidate,evidence=ensure_design_base(source,'pico')
        self.assertNotIn('bootstrap.css',candidate)
        self.assertIn('@picocss/pico@2.1.1',candidate)
        self.assertIn('Original',candidate)
        self.assertEqual(len(evidence['changes']),2)
        self.assertEqual(ensure_design_base(candidate,'pico')[1]['changes'],[])

    def test_types_and_auditable_fallback(self):
        cases = {
            'homepage': '<main><h1>University</h1><p>Welcome</p></main>',
            'listing': '<main>'+'<article><h2>News</h2></article>'*3+'</main>',
            'article': '<main><article><h1>Research</h1>'+'<p>Original text</p>'*4+'</article></main>',
            'form': '<main><form><input name="email"><textarea name="message"></textarea></form></main>',
            'data': '<main><table>'+'<tr><td>Value</td></tr>'*3+'</table></main>',
        }
        for kind, source in cases.items():
            with self.subTest(kind=kind):
                reference = select_reference(source)
                self.assertEqual(reference['page_type'], kind)
                self.assertTrue(reference['reason'])
                self.assertEqual(len(reference['sha256']), 64)
                self.assertFalse(reference['certified_accessible'])
                soup = BeautifulSoup(reference['html'], 'html.parser')
                self.assertEqual(len(soup.find_all('main')), 1)
                self.assertEqual(len(soup.find_all('h1')), 1)
                self.assertFalse(soup.find_all('script'))
                self.assertNotIn('Pricing', reference['html'])
                self.assertNotIn('src="..."', reference['html'])
        self.assertEqual(set(cases), set(EXAMPLES))

    def test_header_search_does_not_override_article(self):
        source = '<header><form><input name="q"><input name="search"></form></header><main><article>'+'<p>Text</p>'*5+'</article></main>'
        self.assertEqual(select_reference(source)['page_type'], 'article')

    def test_markdown_uses_html_for_classification_without_replacing_input(self):
        source = '<main>'+'<article>Original</article>'*3+'</main>'
        messages = generation_messages('# Complete Markdown', 'https://example.org/', True,
                                       adaptive=True, reference_document=source)
        self.assertEqual(messages[2]['content'], '# Complete Markdown')
        self.assertIn(REFINED_INSTRUCTION, messages[0]['content'])
        evidence = generation_evidence(messages, 'markdown', 'local')
        self.assertEqual(evidence['structural_reference_metadata']['page_type'], 'listing')
        self.assertEqual(evidence['version'], 'whole-document-content-faithful-v3')
        self.assertIn('Copy every human-visible source string verbatim', messages[0]['content'])
        self.assertIn('not content or a required layout', messages[3]['content'])

    def test_new_regeneration_requires_a_reference(self):
        messages = generation_messages('<h1>Source</h1>', 'https://example.org/', adaptive=True)
        self.assertEqual(len(messages), 5)
        evidence = generation_evidence(messages, 'html', 'local')
        self.assertTrue(evidence['structural_reference'])
        self.assertEqual(evidence['structural_reference_metadata']['framework'],'bootstrap')
        self.assertIn('hidden tokens', messages[0]['content'])

    def test_pico_references_do_not_leak_bootstrap_classes_or_dependencies(self):
        for source in ('<h1>Source</h1>','<article>News</article>'*3,'<table>'+'<tr><td>Data</td></tr>'*3+'</table>'):
            reference=select_reference(source,'pico')
            self.assertIn('@picocss/pico@2.1.1',reference['html'])
            self.assertNotIn('bootstrap',reference['html'])
            self.assertNotIn('card-body',reference['html'])
            self.assertNotIn('row-cols',reference['html'])
            self.assertFalse(BeautifulSoup(reference['html'],'html.parser').find_all('script'))
        messages=generation_messages('# Original', 'https://example.org/', adaptive=True,framework='pico')
        self.assertEqual(generation_evidence(messages,'markdown','local')['structural_reference_metadata']['framework'],'pico')
        self.assertIn('overrides Bootstrap-specific advice',messages[0]['content'])
        with self.assertRaises(ValueError): select_reference('<h1>Original</h1>','unknown')

    def test_literal_baseline_still_available(self):
        messages = generation_messages('# Source', 'https://example.org/', True)
        self.assertEqual(generation_evidence(messages, 'markdown', 'local')['version'], 'vera-whole-document-v1')
        self.assertIn('Pricing', messages[4]['content'])
