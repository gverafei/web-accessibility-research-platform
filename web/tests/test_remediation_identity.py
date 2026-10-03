"""Shared presentation labels must not drift between sliders and reports."""
from pathlib import Path
import unittest
from jinja2 import Environment, FileSystemLoader
from remediation_approaches import presentation_priority, presentation_name


class RemediationIdentityTests(unittest.TestCase):
    def setUp(self):
        self.templates = Path(__file__).resolve().parents[1] / 'app' / 'templates'
        env = Environment(loader=FileSystemLoader(self.templates), autoescape=True)
        env.globals['_'] = lambda text: text
        self.identity = env.get_template('_remediation_identity.html').module

    def test_shared_names_and_colors(self):
        self.assertEqual(list(self.identity.preservation_names.values()), [
            'Minimal patches', 'Localized repair', 'Coordinated repair',
            'HTML regeneration', 'Markdown regeneration'])
        self.assertEqual(list(self.identity.preservation_colors.values()),
                         [color for tier, color in self.identity.tier_colors.items() if tier != 'local'])
        for filename in ('remediation_runs.html', '_remediation_history_rows.html', 'remediation_detail.html'):
            self.assertIn("from '_remediation_identity.html' import", (self.templates / filename).read_text())

    def test_all_remediation_templates_compile(self):
        env=Environment(loader=FileSystemLoader(self.templates),autoescape=True)
        for filename in ('remediation_runs.html','remediation_history.html','_remediation_history_rows.html','remediation_detail.html'):
            env.get_template(filename)

    def test_run_id_and_start_time_are_visible_in_list_and_detail(self):
        history=(self.templates/'_remediation_history_rows.html').read_text()
        header=(self.templates/'_remediation_report_header.html').read_text()
        for template in (history,header):
            self.assertIn('#{{ run.id }}',template)
            self.assertIn('run.created_at',template)

    def test_source_picker_is_not_a_single_result_shortcut(self):
        template=(self.templates/'remediation_runs.html').read_text()
        for retired in ('existingRemediationNotice','forceRemediation','data-accepted-url','accepted-version-label','selectedSourceName'):
            self.assertNotIn(retired,template)
        route=(self.templates.parent/'routes'/'remediation.py').read_text()
        self.assertNotIn('reusable_accepted_run',route.split('def new_run():',1)[1])

    def test_live_status_does_not_require_an_iteration_item(self):
        env=Environment(autoescape=True)
        env.globals['_']=lambda text:text
        status=next(line for line in (self.templates/'remediation_detail.html').read_text().splitlines() if line.startswith('{% if active %}'))
        html=env.from_string(status).render(active=True,run={'progress_message':None,'current_iteration':0,'max_iterations':2,'progress_percent':0})
        self.assertIn('Waiting for an available worker',html)
        self.assertIn('Iteration',html)

    def test_execution_strategy_is_section_three_with_two_choices(self):
        from bs4 import BeautifulSoup
        dom=BeautifulSoup((self.templates/'remediation_runs.html').read_text(),'html.parser')
        execution=dom.select_one('#executionStep')
        self.assertEqual(execution.select_one('legend span').get_text(),'3')
        self.assertEqual([option['value'] for option in execution.select('input[name="execution_mode"]')],
                         ['iterative','single_shot'])
        self.assertEqual(dom.select_one('#preservationStep legend span').get_text(),'4')
        self.assertIsNotNone(dom.select_one('#preservationStep #regenerationReference'))
        self.assertIsNone(execution.select_one('#regenerationReference'))
        self.assertEqual([option['value'] for option in dom.select('#regenerationFramework option')],['bootstrap','pico','bulma'])
        self.assertIsNone(dom.select_one('input[name="regeneration_reference"]'))
        self.assertIsNone(dom.select_one('input[name="use_rag"]'))
        self.assertIsNotNone(dom.select_one('#ragStep'))
        self.assertTrue(dom.select_one('#actGrounding').has_attr('checked'))
        self.assertEqual(dom.select_one('#actGrounding')['role'],'switch')
        self.assertIsNone(execution.select_one('select'))
        self.assertIsNone(dom.select_one('input[name="use_expert_settings"]'))
        self.assertIsNone(dom.select_one('#modelTierSubtitle'))

    def render_header(self, error, best=None, status='completed_with_warnings', **run_fields):
        env=Environment(loader=FileSystemLoader(self.templates),autoescape=True)
        env.globals['_']=lambda text:text
        env.globals['url_for']=lambda *args,**kwargs:'/compare'
        return env.get_template('_remediation_report_header.html').render(
            run={'id':256,'source_name':'Source page','source_url':'https://example.org/',
                 'title':'Long pilot name','temperature':.5,'transformation_format':'markdown',
                 'execution_mode':'regenerate_refine','presentation_priority':90,
                 'presentation_name':'Markdown regeneration','status':status,
                 'error_message':error,**run_fields},best=best)

    def test_warning_explains_only_unmet_measured_targets(self):
        html=self.render_header(None,{'axe_violations':10,'lighthouse_score':96},max_axe=3,min_lighthouse=94)
        self.assertIn('Axe target not reached: 10',html)
        self.assertIn('Axe ≤ 3',html)
        self.assertNotIn('Lighthouse target not reached',html)
        self.assertIn('Unmet targets do not reject the candidate',html)

    def test_lighthouse_and_content_warnings_are_visible(self):
        html=self.render_header(None,{'axe_violations':0,'lighthouse_score':87,
            'strategy':{'content_gate':{'passed':False}}},max_axe=3,min_lighthouse=94)
        self.assertIn('Lighthouse target not reached: 87',html)
        self.assertIn('Content preservation is below',html)
        self.assertNotIn('Axe target not reached',html)

    def test_warning_fallback_and_accepted_run(self):
        self.assertIn('recorded warning',self.render_header(None,{'id':42}))
        self.assertNotIn('alert-warning',self.render_header(None,{'id':42},status='accepted'))

    def test_provider_error_is_red_and_distinguishes_retained_candidate(self):
        from bs4 import BeautifulSoup
        dom=BeautifulSoup(self.render_header('402 Client Error: Payment Required',{'id':42}),'html.parser')
        error=dom.select_one('.alert-danger[role=alert]')
        self.assertIsNotNone(error)
        self.assertIn('evaluated result retained',error.get_text())
        self.assertIn('HTTP 402',error.get_text())
        self.assertIn('402 Client Error',error.select_one('details pre').get_text())

    def test_connection_error_without_candidate_never_promises_result(self):
        html=self.render_header('ConnectionError: network unavailable',status='failed')
        self.assertIn('no evaluated candidate available',html)
        self.assertIn('No evaluated result can be returned',html)
        self.assertNotIn('candidate remains available below',html)

    def test_timeout_and_generic_api_errors_have_clear_explanations(self):
        self.assertIn('API did not respond',self.render_header('Read timed out',status='failed'))
        self.assertIn('process encountered an error',self.render_header('503 Service unavailable',status='failed'))

    def test_no_error_banner_for_content_warnings_only(self):
        self.assertNotIn('alert-danger',self.render_header(None,{'id':42}))

    def test_failure_without_technical_details_still_shows_red_error(self):
        html=self.render_header(None,status='failed')
        self.assertIn('alert-danger',html)
        self.assertIn('No evaluated result can be returned',html)
        self.assertNotIn('Technical error details',html)

    def test_capture_click_and_live_page_links_have_distinct_targets(self):
        from bs4 import BeautifulSoup
        env=Environment(loader=FileSystemLoader(self.templates),autoescape=True)
        env.globals['_']=lambda text:text
        preview=env.get_template('_remediation_preview.html').module.capture_preview
        dom=BeautifulSoup(str(preview('Original','/capture.jpg','https://example.test/','Capture','Open original')),'html.parser')
        self.assertEqual(dom.select_one('a.page-preview')['href'],'/capture.jpg')
        self.assertEqual(dom.select_one('a.preview-open-icon')['href'],'https://example.test/')
        for link in dom.select('a'):
            self.assertEqual(link['target'],'_blank')
            self.assertIn('noopener',link['rel'])
        self.assertEqual(len(dom.select('.page-preview-popover img')),1)
        no_capture=BeautifulSoup(str(preview('Candidate',None,'/candidate','Capture','Open candidate')),'html.parser')
        self.assertFalse(no_capture.select('a.page-preview'))
        self.assertEqual(no_capture.select_one('a.preview-open-icon')['href'],'/candidate')

    def test_model_version_provider_and_safe_markup(self):
        for model, company in [('openai/gpt-6-luna', 'OpenAI'),
                               ('google/gemini-3.8-flash', 'Google'),
                               ('meta-llama/llama-4-maverick', 'Meta'),
                               ('qwen/qwen3-coder-next', 'Qwen'),
                               ('anthropic/claude-opus-5.5', 'Anthropic')]:
            html = str(self.identity.model_identity(model))
            self.assertIn(company, html)
            self.assertIn(model, html)
            self.assertIn('model-company-icon', html)
        self.assertNotIn('<script>', str(self.identity.model_identity('unknown/<script>')))

    def test_local_qwen_uses_family_icon_without_losing_endpoint_identity(self):
        html=str(self.identity.model_identity('ollama/qwen3.5:4b'))
        self.assertIn('model-company-qwen', html)
        self.assertIn('Qwen', html)
        self.assertIn('ollama/qwen3.5:4b', html)

    def test_direct_selection_has_one_label_in_list_and_report(self):
        for filename in ('_remediation_history_rows.html','remediation_detail.html'):
            template=(self.templates/filename).read_text()
            self.assertNotIn('_("User selected")',template)
            self.assertIn('run.model_presentation.tier',template)
            self.assertIn('run.model_presentation.color',template)
            self.assertNotIn('selection_label',template)

    def test_model_strategy_uses_recorded_tier_not_hardcoded_provider_ranking(self):
        for mode in ('user','manual','automatic'):
            for model,tier in [('google/gemini-3.8-flash','high'),('openai/gpt-6-luna','low'),('openai/gpt-6-sol','max'),('ollama/qwen3.5:4b','local')]:
                run={'model_selection_mode':mode,'use_expert_settings':True,'generator_model':model,'model_cost_tier':tier}
                self.assertEqual(str(self.identity.model_strategy_tier(run)).strip(),tier)
        self.assertEqual(str(self.identity.model_strategy_tier({'generator_model':'legacy/model','model_cost_tier':'medium'})).strip(),'medium')
        self.assertEqual(str(self.identity.model_strategy_tier({'generator_model':'openai/gpt-6-sol','model_cost_tier':'medium'})).strip(),'medium')

    def test_anthropic_icon_is_vector_and_unknown_providers_have_a_monogram(self):
        from bs4 import BeautifulSoup
        known = BeautifulSoup(str(self.identity.model_identity('anthropic/claude-opus-5.5')), 'html.parser')
        self.assertIsNotNone(known.select_one('.model-company-anthropic svg'))
        unknown = BeautifulSoup(str(self.identity.model_identity('future/model')), 'html.parser')
        self.assertEqual(unknown.select_one('.model-company-future').get_text(), 'F')

    def test_additional_local_models_keep_their_company_icons(self):
        for model,provider in [('ollama/gemma3:4b','google'),('ollama/llama3.2:3b','meta-llama')]:
            html=str(self.identity.model_identity(model))
            self.assertIn('model-company-'+provider,html)
            self.assertIn(model,html)

    def test_capture_preview_is_not_centered_over_cursor(self):
        css=(self.templates.parent/'static'/'css'/'remediation_layout.css').read_text()
        template=(self.templates.parent/'static/js/remediation_detail.js').read_text()
        self.assertNotIn('translate(-50%,-50%)',css)
        self.assertIn('pointer-events:none',css)
        self.assertIn("'pointermove'",template)
        self.assertIn('x+gap',template)

    def test_historical_blocks_map_to_step_four_without_mutating_history(self):
        strategy={'approach':{'name':'Born-accessible regeneration','step':5},'born_content_contract':{'version':'protected-blocks-v1'}}
        priority=presentation_priority(90,strategy)
        self.assertEqual(priority,75)
        self.assertEqual(presentation_name(90,strategy),'Content-preserving recomposition')
        self.assertEqual(self.identity.preservation_colors[priority],'#9b4fc2')
        self.assertEqual(strategy['approach']['step'],5)

    def test_verified_components_map_to_step_five(self):
        priority=presentation_priority(90,{'born_content_contract':{'version':'protected-data-components-v2'}})
        self.assertEqual(presentation_name(90,{'born_content_contract':{'version':'protected-data-components-v2'}}),'Born-accessible')
        self.assertEqual(self.identity.preservation_colors[priority],'#c3486b')
        self.assertEqual(presentation_priority(35,{}),35)
        self.assertEqual(presentation_priority(90,{'born_content_contract':None}),90)
