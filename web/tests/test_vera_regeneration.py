import unittest
from unittest.mock import patch,Mock
from vera_regeneration import generation_messages,generation_evidence,complete_candidate,omission_context,resource_omissions,task_omissions,preservation_refinement_needed
from vera_prompt import SYSTEM_PROMPT


class WholeRegenerationTests(unittest.TestCase):
    def test_provider_request_preserves_temperature(self):
        from remediation_jobs import call_model
        response=Mock()
        response.json.return_value={'model':'openai/gpt-6-sol','choices':[{'message':{'content':'complete response'}}],'usage':{}}
        with patch('remediation_jobs.requests.post',return_value=response) as post:
            call_model({'openrouter_base_url':'https://example.test','openrouter_api_key':'test'},'openai/gpt-6-sol','exact prompt',temperature=.7,cost_tier='low',output_token_limit=6000)
        self.assertEqual(post.call_args.kwargs['json']['temperature'],.7)
        self.assertEqual(post.call_args.kwargs['json']['max_tokens'],6000)

    def test_metrics_success_does_not_skip_content_or_task_refinement(self):
        self.assertTrue(preservation_refinement_needed('regenerate_refine',False,[]))
        self.assertTrue(preservation_refinement_needed('regenerate_refine',True,[{'action':'/search'}]))
        self.assertFalse(preservation_refinement_needed('regenerate_refine',True,[]))
        self.assertFalse(preservation_refinement_needed('regenerate_only',False,[{}]))

    def test_native_form_omissions_are_detected_without_restoring_layout(self):
        source='<form action="/search.php"><input name="q"><input type="submit" name="go" value="GO"></form>'
        candidate='<form action="https://example.org/search.php"><input name="q"><button>Search</button></form>'
        missing=task_omissions(source,candidate,'https://example.org/')
        self.assertEqual(missing[0]['fields'][1]['name'],'go')
        self.assertEqual(missing[0]['action'],'https://example.org/search.php')
        self.assertEqual(task_omissions(source,source,'https://example.org/'),[])

    def test_refiner_receives_exact_omitted_content_without_source_layout(self):
        text='These twelve original words are useful information for readers visiting our support page today.'
        source='<style>old theme</style><p>'+text+'<a href="/support">Help</a></p>'
        evidence=omission_context(source,'<p>Visit support</p>','https://example.org/')
        self.assertEqual(evidence[0]['text'],text+' Help')
        self.assertEqual(evidence[0]['destinations'],['https://example.org/support'])
        self.assertNotIn('old theme',str(evidence))
        self.assertEqual(omission_context(source,source,'https://example.org/'),[])
    def test_original_message_roles_and_separate_complete_input(self):
        messages=generation_messages('<html>Exact source</html>','https://example.org/')
        self.assertEqual([m['role'] for m in messages],['system','user','user','user','user'])
        self.assertTrue(messages[0]['content'].startswith(SYSTEM_PROMPT))
        self.assertEqual(messages[1]['content'],"Use the following content to create a new accessible web page version. The root URL is 'https://example.org/'.")
        self.assertEqual(messages[2]['content'],'<html>Exact source</html>')
        self.assertNotIn('data-warp-slot',SYSTEM_PROMPT)
        self.assertNotIn('Axe',SYSTEM_PROMPT)

    def test_missing_resources_keep_short_labels_and_image_relationships(self):
        source='<style>old theme</style><a href="/help">Help</a><a href="/help">Help</a><a href="/photo"><img src="/picture.jpg" alt="Office" title="Original title"></a>'
        missing=resource_omissions(source,'<main>New page</main>','https://example.org/')
        self.assertEqual(missing['links'][0],{'url':'https://example.org/help','text':'Help','title':''})
        self.assertEqual(len(missing['links']),2)
        self.assertEqual(missing['links'][1]['image_src'],'https://example.org/picture.jpg')
        self.assertEqual(missing['images'][0],{'url':'https://example.org/picture.jpg','alt':'Office','title':'Original title','link_destination':'https://example.org/photo'})
        self.assertNotIn('old theme',str(missing))
        self.assertEqual(resource_omissions(source,source,'https://example.org/'),{'links':[],'images':[]})

    def test_missing_resources_are_recomputed_after_invalid_output_without_history(self):
        source='<a href="/help">Help</a><img src="/picture.jpg" alt="Office">'
        first='<a href="https://example.org/help">Help</a>'
        self.assertEqual(resource_omissions(source,first,'https://example.org/')['links'],[])
        self.assertEqual(len(resource_omissions(source,first,'https://example.org/')['images']),1)
        restored=first+'<img src="https://example.org/picture.jpg" alt="Office">'
        self.assertEqual(resource_omissions(source,restored,'https://example.org/'),{'links':[],'images':[]})
        from pathlib import Path
        import remediation_jobs
        worker_source=Path(remediation_jobs.__file__).read_text()
        self.assertIn('resource_omissions(rendered_source,base_document,source_base)',worker_source)
        self.assertNotIn('generator_messages',worker_source)

    def test_placeholder_links_do_not_falsely_count_as_the_source_home_url(self):
        source='<a href="/">Home</a><a href=" /help ">Help</a><a href="#section">Section</a><a href="javascript:void(0)">Toggle</a>'
        candidate='<a href="#">Home</a><a href="">Empty</a><a href="javascript:void(0)">Toggle</a><img src=""><img src="data:image/png;base64,AAAA">'
        missing=resource_omissions(source,candidate,'https://example.org/')
        self.assertEqual({item['url'] for item in missing['links']},{'https://example.org/','https://example.org/help'})
        self.assertEqual(missing['images'],[])

    def test_structural_reference_is_selected_for_the_current_design_base(self):
        messages=generation_messages('# Source','https://example.org/')
        self.assertEqual(len(messages),5)
        self.assertIn('bootstrap',messages[4]['content'])
        evidence=generation_evidence(messages,'markdown','jina')
        self.assertTrue(evidence['structural_reference'])
        self.assertEqual(evidence['temperature'],.5)
        self.assertNotIn('reproduction',evidence)
        self.assertNotIn('differences',evidence)

    def test_experimental_temperature_is_recorded_not_silently_reset(self):
        messages=generation_messages('# Exact source','https://example.org/')
        evidence=generation_evidence(messages,'markdown','local',.7)
        self.assertEqual(evidence['temperature'],.7)
        self.assertEqual(evidence['messages'],messages)
        self.assertEqual(generation_evidence(messages,'markdown','local')['temperature'],.5)

    def test_complete_output_can_rebuild_original_structures_and_fix_labels(self):
        source='<html><body><div><input name="q"></div></body></html>'
        generated='<!doctype html><html><head><title>Source</title></head><body><main><label for="q">Search</label><input id="q" name="q"></main></body></html>'
        self.assertEqual(complete_candidate(generated,source,'https://example.org/'),generated)
        self.assertEqual(complete_candidate('```html\n'+generated+'\n```',source,'https://example.org/'),generated)

    def test_empty_truncated_and_original_embedding_are_not_substituted(self):
        for content in ('','x'*180001):
            with self.assertRaises(ValueError): generation_messages(content,'https://example.org/')
        for response in ('<p>Snippet</p>','<!doctype html><html><body>Incomplete','<!doctype html><html><body><iframe src="https://example.org/"></iframe></body></html>'):
            with self.assertRaises(ValueError): complete_candidate(response,'<html><body>Original</body></html>','https://example.org/')

    def test_complete_document_with_explanatory_prose_is_extracted_not_rejected(self):
        generated='<!doctype html><html><head><title>Source</title></head><body><main>Source</main></body></html>'
        for response in ('Here is the page:\n'+generated+'\nNote: test keyboard behavior.',
                         '```html\n'+generated+'\n```\nNote: test keyboard behavior.'):
            self.assertEqual(complete_candidate(response,'<p>Original</p>','https://example.org/'),generated)
        for response in (generated+generated, generated+'<!doctype html><html><body>Incomplete'):
            with self.assertRaises(ValueError):
                complete_candidate(response,'<p>Original</p>','https://example.org/')

    def test_script_literals_do_not_end_the_extracted_document_early(self):
        generated='<!doctype html><html><head><script>const example="</html>";</script></head><body><main>Source</main></body></html>'
        self.assertEqual(complete_candidate(generated+'\nNote: complete page.','<p>Source</p>','https://example.org/'),generated)
