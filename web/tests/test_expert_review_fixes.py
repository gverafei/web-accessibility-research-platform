"""Offline regressions: no live experiments, paid calls or persistent studies."""
import base64
import hashlib
import io
import json
import tempfile
import tracemalloc
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests
from bs4 import BeautifulSoup
from flask import Flask
from flask_babel import Babel
from jinja2 import Environment, FileSystemLoader

from local_llm import installed_local_models
from remediation_report_presentation import iteration_presentation, event_presentation, load_model_calls, retention_summary
from result_portability import validate_portable_payload, validate_archive_artifacts, decode_artifacts
from routes.remediation import remediation_bp
from tranco_sampling import TRANCO_STRATA, form_strata, sample_tranco
from warp_export import archive_chunks, dataset_members

TEMPLATES = Path(__file__).resolve().parents[1] / 'app/templates'


class ExpertReviewTests(unittest.TestCase):
    def test_new_strata_labels_and_legacy_design_are_independent(self):
        self.assertEqual([(r[2],r[3]) for r in TRANCO_STRATA],
                         [(1,1000),(1001,10000),(10001,100000),(100001,500000),(500001,1000000)])
        changed = form_strata({'tranco_label_rank_1_1000':'My top group'})
        self.assertEqual(changed[0][1], 'My top group')
        old = (('rank_1_500','Legacy top',1,500),('old_tail','Legacy tail',501,1000000))
        ranking = [(1,'a.test'),(501,'b.test')]
        _, metadata = sample_tranco(ranking,'OLD123','seed',1,0,strata_definitions=old)
        self.assertEqual([(r['display_name'],r['rank_min'],r['rank_max']) for r in metadata],
                         [('Legacy top',1,500),('Legacy tail',501,1000000)])
        with self.assertRaises(ValueError):
            form_strata({'tranco_label_rank_1_1000':' '})

    def test_streamed_archive_is_valid_legacy_v3_with_exact_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); raw = root/'raw'; raw.mkdir()
            artifact = raw/'axe.json'; content = bytes(range(256))*1025 + b'last'
            artifact.write_bytes(content)
            external = root/'private.txt'; external.write_text('not an artifact')
            payload = {'format':'warp-experiment','version':3,'experiment':{'id':3}}
            rows = [{'url':'https://example.org/','axe_raw_path':str(artifact),
                     'semantic_raw_path':str(external)}]
            packed = b''.join(archive_chunks(payload,rows,artifact_root=raw))
            with zipfile.ZipFile(io.BytesIO(packed)) as archive:
                self.assertIsNone(archive.testzip())
                manifest = json.loads(archive.read('experiment.json'))
            validate_portable_payload(manifest)
            files = manifest['results'][0]['artifacts']
            self.assertEqual(base64.b64decode(files['axe_raw_path']['base64']),content)
            self.assertNotIn('semantic_raw_path', files)

    def test_streamed_artifact_memory_does_not_grow_with_file_size(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'large.json'
            with path.open('wb') as source:
                for _ in range(256): source.write(b'abcdefgh'*16384)  # 32 MiB
            tracemalloc.start()
            for chunk in archive_chunks({'format':'warp-experiment','version':4,'experiment':{}},
                    [{'url':'https://example.org/','axe_raw_path':str(path)}], artifact_root=directory):
                self.assertLess(len(chunk),200000)
            _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
            self.assertLess(peak,2*1024*1024)

    def test_v4_binary_roundtrip_and_hash_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'axe.json'; content=b'actual evidence'*5000; path.write_bytes(content)
            packed=b''.join(archive_chunks({'format':'warp-experiment','version':4,'experiment':{}},
                [{'url':'https://example.org/','axe_raw_path':str(path)}],artifact_root=directory))
            with zipfile.ZipFile(io.BytesIO(packed)) as archive:
                manifest=json.loads(archive.read('experiment.json'))
                validate_portable_payload(manifest); validate_archive_artifacts(manifest,archive)
                artifact=manifest['results'][0]['artifacts']['axe_raw_path']
                self.assertNotIn('base64',artifact)
                self.assertEqual(artifact['sha256'],hashlib.sha256(content).hexdigest())
                self.assertEqual(archive.read(artifact['member']),content)
                with patch('result_portability.os.path.realpath',return_value=directory):
                    result=decode_artifacts({}, {'axe_raw_path':artifact},9,archive)
                    self.assertEqual(Path(result['axe_raw_path']).read_bytes(),content)
                    artifact['sha256']='0'*64
                    with self.assertRaisesRegex(ValueError,'SHA-256'):
                        decode_artifacts({}, {'axe_raw_path':artifact},9,archive)
                artifact['size']+=1
                with self.assertRaisesRegex(ValueError,'size'):
                    validate_archive_artifacts(manifest,archive)

    def test_v4_missing_member_and_storage_budget_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'axe.json'; path.write_bytes(b'actual evidence')
            packed=b''.join(archive_chunks({'format':'warp-experiment','version':4,'experiment':{}},
                [{'url':'https://example.org/','axe_raw_path':str(path)}],artifact_root=directory))
            with zipfile.ZipFile(io.BytesIO(packed)) as archive:
                manifest=json.loads(archive.read('experiment.json'))
                with self.assertRaisesRegex(ValueError,'budget'):
                    validate_archive_artifacts(manifest,archive,max_total_bytes=1)
                artifact=manifest['results'][0]['artifacts']['axe_raw_path']
                artifact['member']='artifacts/absent'
                with self.assertRaises(KeyError): validate_archive_artifacts(manifest,archive)

    def test_report_heading_and_score_hierarchy_are_shared(self):
        env=Environment(loader=FileSystemLoader(TEMPLATES),autoescape=True)
        env.globals['_']=lambda text:text
        heading=env.get_template('_report_heading.html').module.report_heading
        for title in ('Original page','Evaluation name'):
            dom=BeautifulSoup(heading('Report #1',title,'Date','Action'),'html.parser')
            self.assertEqual(dom.select_one('header h1').get_text(),title)
            self.assertIn('remediation-report-heading',dom.header['class'])
        score=env.get_template('_remediation_score_cards.html').module.score_card
        dom=BeautifulSoup(score('Original',23,91,6.7),'html.parser')
        self.assertEqual([item.get_text() for item in dom.select('.remediation-score-list strong')],['23','91','6.7'])
        self.assertFalse(dom.select('.remediation-score-list small'))
        detail=(TEMPLATES/'remediation_detail.html').read_text()
        self.assertNotIn('Observed outcome; does not affect acceptance',detail)
        self.assertIn('retention-metric',detail)
        self.assertIn('contentRetentionTitle',(TEMPLATES/'_remediation_retention.html').read_text())

    def test_retention_table_renders_with_spanish_newstyle_gettext(self):
        from babel.messages.pofile import read_po
        from babel.messages.mofile import write_mo
        from babel.support import Translations
        with (TEMPLATES.parent/'translations/es/LC_MESSAGES/messages.po').open() as source:
            catalog=read_po(source,locale='es')
        compiled=io.BytesIO(); write_mo(compiled,catalog); compiled.seek(0)
        env=Environment(loader=FileSystemLoader(TEMPLATES),extensions=['jinja2.ext.i18n'],autoescape=True)
        env.install_gettext_translations(Translations(compiled),newstyle=True)
        summary=retention_summary({'text_percent':98.35,'original_words':1092,'candidate_words':1074,
            'links_percent':100,'images_percent':100,'dynamic_images_percent':100})
        html=env.get_template('_remediation_retention.html').render(best={'retention_summary':summary})
        self.assertIn('1,092',html); self.assertIn('1,074',html)
        self.assertNotIn('Text retention counts',html)
        self.assertIn('98.35%',html)

    def test_evaluation_loading_and_ready_share_recorded_header_indicators(self):
        env=Environment(loader=FileSystemLoader(TEMPLATES),autoescape=True)
        env.globals.update(_=lambda text:text, url_for=lambda *args,**kwargs:'/test')
        experiment={'id':131,'title':'Custom sample','created_at':'2026-10-02',
            'source_type':'tranco','axe_standard':'wcag22aa',
            'axe_include_best_practices':False,'include_wave':True,'reuse_cached_results':False}
        for loading in (False,True):
            dom=BeautifulSoup(env.get_template('_evaluation_report_header.html').render(
                experiment=experiment,report_loading=loading,pending=False),'html.parser')
            self.assertIn('remediation-report-heading',dom.header['class'])
            self.assertEqual([tag.get_text() for tag in dom.select('.remediation-report-tags>span')],
                ['Tranco','WCAG 2.2 AA','Best Practices: Disabled','WAVE: Enabled','Stored-result reuse: Disabled'])
            self.assertEqual(len(dom.select('a')),0 if loading else 2)
        transition=(TEMPLATES/'report_transition.html').read_text()
        self.assertIn("include '_evaluation_report_header.html'",transition)
        self.assertNotIn('report-hero',transition)
        self.assertNotIn('<td><strong>{{ _(stratum.display_name', (TEMPLATES/'report.html').read_text())

    def test_retention_average_is_read_only_and_missing_measures_are_not_zero(self):
        measured={'text_percent':98.35,'links_percent':100,'images_percent':100,'dynamic_images_percent':100}
        before=dict(measured)
        summary=retention_summary(measured)
        self.assertEqual(summary['percent'],99.59); self.assertEqual(summary['measures'],4)
        self.assertEqual(measured,before)
        partial=retention_summary({'text_percent':0,'links_percent':100})
        self.assertEqual(partial['percent'],50); self.assertEqual(partial['measures'],2)
        self.assertIsNone(partial['rows'][2]['percent'])
        self.assertIsNone(retention_summary(None)['percent'])
        self.assertEqual(retention_summary({'text_percent':float('nan'),'images_percent':True})['measures'],0)

    def test_dataset_export_rejects_symlink_outside_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/'dataset'; source.mkdir()
            other=root/'secret'; other.write_text('secret')
            (source/'outside').symlink_to(other)
            with self.assertRaises(ValueError): dataset_members('dataset',root)

    def test_ollama_failure_for_one_capability_does_not_hide_models(self):
        tags=MagicMock(); tags.json.return_value={'models':[{'name':'a:4b'},{'name':'b:4b'}]}
        details=MagicMock(); details.json.return_value={'capabilities':['completion','vision']}
        with patch('local_llm.requests.get',return_value=tags) as get, \
             patch('local_llm.requests.post',side_effect=[requests.ConnectionError('offline'),details]) as post:
            models=installed_local_models('http://host.docker.internal:11434')
        self.assertEqual([row['id'] for row in models],['a:4b','b:4b'])
        self.assertFalse(models[0]['capabilities_verified']); self.assertTrue(models[1]['vision'])
        self.assertTrue(get.call_args.args[0].endswith('/api/tags'))
        self.assertTrue(all(call.args[0].endswith('/api/show') for call in post.call_args_list))

    def test_evidence_descriptions_keep_versions_and_cost_types(self):
        item={'strategy':{'agentic_runtime':{'iteration_skills':[{'id':'minimal-preservation-repair','version':'1','sha256':'abc'}],
                 'tool_contracts':[{'name':'measure','description':'Measures the page'}],
                 'tool_invocations':[{'tool':'measure','version':'2','status':'completed','seconds':1}]},
                 'stage_accounting':{'planning':{'llm_calls':0,'seconds':0,'cost_usd':0},
                     'generation':{'llm_calls':1,'seconds':2,'cost_usd':.01},
                     'automated_evaluation':{'llm_calls':0,'seconds':1,'cost_usd':0}}}}
        iteration_presentation(item,7,'/datasets')
        self.assertEqual(item['runtime_skills'][0]['sha256'],'abc')
        self.assertEqual(item['runtime_tools'][0]['description'],'Measures the page')
        self.assertEqual([s['kind'] for s in item['pipeline_stages']],['LLM calls','Software tool'])
        event={'event_type':'decision','details_json':'{"coordinator":"some/model"}'}
        event_presentation(event)
        self.assertEqual(event['activity_kind'],'Software coordinator')
        self.assertIsNone(event['activity_model'])

    def test_call_evidence_cannot_read_another_run(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'remediations/9/iteration_1/model-call-evidence.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'calls':[{'call_number':1,'prompt':'real input'}]}))
            strategy={'model_call_evidence':{'path':str(path)}}
            self.assertEqual(load_model_calls(strategy,9,directory)[0]['prompt'],'real input')
            self.assertEqual(load_model_calls(strategy,8,directory),[])

    def test_capture_metrics_distinguish_html_structure_from_rgb(self):
        env=Environment(loader=FileSystemLoader(TEMPLATES),autoescape=True)
        env.globals['_']=lambda text:text
        item={'original_dom_nodes':5184,'candidate_dom_nodes':5186,
            'strategy':{'candidate_selection':{'visual_similarity_percent':97.125}}}
        iteration_presentation(item,7,'/datasets')
        dom=BeautifulSoup(env.get_template('_remediation_capture_metrics.html').render(item=item),'html.parser')
        self.assertIn('Original: 5,184 · Candidate: 5,186',dom.get_text())
        self.assertIn('Visual similarity (RGB)',dom.get_text())
        self.assertIn('97.12%',dom.get_text())
        self.assertNotIn('structural tokens',dom.get_text())
        self.assertEqual(len(dom.select('.capture-comparison-metrics>div')),2)
        self.assertIn('affect the comparison, not the count',dom.select_one('.capture-comparison-metrics>div')['title'])

    def test_capture_metrics_below_previews_and_disclosure_spacing_is_shared(self):
        css=(TEMPLATES.parent/'static/css/remediation_layout.css').read_text()
        self.assertIn('.remediation-detail .iteration-actions{display:block}',css)
        self.assertIn('.capture-comparison-metrics{display:grid;',css)
        self.assertIn('.remediation-detail .iteration-timeline>article>details{margin:.55rem 0 0;padding:0}',css)
        self.assertIn('.remediation-detail .iteration-timeline>article>details>summary{padding:.22rem 0;line-height:1.45}',css)

    def test_absent_or_invalid_rgb_is_not_fabricated(self):
        env=Environment(loader=FileSystemLoader(TEMPLATES),autoescape=True)
        env.globals['_']=lambda text:text
        for value in (None,True,float('nan'),101,-1,0):
            item={'original_dom_nodes':None,'candidate_dom_nodes':None,
                'strategy':{'candidate_selection':{'visual_similarity_percent':value}}}
            iteration_presentation(item,7,'/datasets')
            html=env.get_template('_remediation_capture_metrics.html').render(item=item)
            self.assertEqual('Visual similarity (RGB)' in html,value == 0 and value is not None and value is not True)
            if value == 0:
                self.assertIn('0.00%',html)

    def test_activity_badges_and_positive_descriptions(self):
        env=Environment(loader=FileSystemLoader(TEMPLATES),autoescape=True)
        env.globals['_']=lambda text:text
        expected={'generate':'LLM','evaluate':'Tool','decision':'Control','invalid_output':'Validation','custom':'Function',
            'extraction_quality':'Validation','source_hydration':'Function','patch_source_selection':'Function','unmatched_lighthouse_nodes':'Function'}
        events=[]
        for kind,label in expected.items():
            event={'event_type':kind,'actor':'Pipeline','message':'Recorded message','created_at':'2026-10-02'}
            event_presentation(event); events.append(event)
            self.assertEqual(event['activity_label'],label)
        dom=BeautifulSoup(env.get_template('_remediation_activity_log.html').render(events=events),'html.parser')
        self.assertEqual([n.get_text(strip=True) for n in dom.select('.activity-type-badge')],list(expected.values()))
        self.assertEqual(len(dom.select('.activity-type-badge svg')),len(expected))
        self.assertNotIn('not an LLM assessment',dom.get_text())

    def test_coordinator_log_hides_feedback_excerpt_without_mutating_original(self):
        raw='Candidate 2 sent to Generator test/model for refinement in iteration 3: Refine the preceding candidate using the exact evidence below. Axe failures: [{"rule":"image-alt",...'
        event={'actor':'Acceptance coordinator','event_type':'decision','message':raw}
        event_presentation(event)
        self.assertEqual(event['message'],raw)
        self.assertEqual(event['activity_message'],'Candidate 2 sent to Generator test/model for refinement in iteration 3')
        other={'actor':'Evaluator','event_type':'evaluate','message':raw}
        event_presentation(other); self.assertEqual(other['activity_message'],raw)
        strategy=(TEMPLATES/'_remediation_strategy.html').read_text()
        self.assertNotIn("_('Intervention approach')",strategy)
        self.assertNotIn('_("Intervention approach")',(TEMPLATES/'remediation_detail.html').read_text())
        self.assertNotIn('Technical provenance',(TEMPLATES/'_remediation_runtime_evidence.html').read_text())

    def test_compare_reuses_exact_pair_and_redirects_to_report(self):
        app=Flask(__name__); app.secret_key='test'; Babel(app); app.register_blueprint(remediation_bp)
        app.add_url_rule('/comparisons/<int:comparison_id>',endpoint='comparisons.comparison_detail',view_func=lambda comparison_id:'report')
        cursor=MagicMock(); conn=MagicMock(); conn.cursor.return_value=cursor
        cursor.fetchone.side_effect=[{'id':7,'source_result_id':9,'source_name':'Original'}, {'comparison_id':4}]
        with patch('routes.remediation.get_connection',return_value=conn), \
             patch('routes.comparisons.insert_members') as insert:
            response=app.test_client().post('/remediation/7/compare')
        self.assertEqual(response.headers['Location'],'/comparisons/4')
        self.assertIn('FOR UPDATE',cursor.execute.call_args_list[0].args[0])
        self.assertIn('COUNT(*)=2',cursor.execute.call_args_list[1].args[0])
        insert.assert_not_called()

    def test_new_comparison_opens_report_and_requires_complete_pair(self):
        for inserted,location in ((1,'/comparisons/42'),(0,'/remediation/7')):
            with self.subTest(inserted=inserted):
                app=Flask(__name__); app.secret_key='test'; Babel(app); app.register_blueprint(remediation_bp)
                app.add_url_rule('/comparisons/<int:comparison_id>',endpoint='comparisons.comparison_detail',view_func=lambda comparison_id:'report')
                cursor=MagicMock(); conn=MagicMock(); conn.cursor.return_value=cursor
                cursor.fetchone.side_effect=[{'id':7,'source_result_id':9,'source_name':'Original'},None]
                cursor.lastrowid=42
                with patch('routes.remediation.get_connection',return_value=conn), \
                     patch('routes.comparisons.insert_members',return_value=1), \
                     patch('routes.comparisons.insert_remediation_members',return_value=inserted):
                    response=app.test_client().post('/remediation/7/compare')
                self.assertEqual(response.headers['Location'],location)
                (conn.commit if inserted else conn.rollback).assert_called_once()

    def test_rag_uninitialized_and_empty_are_unavailable(self):
        from remediation_rag import status
        for http,count in ((404,0),(200,0),(200,396)):
            response=MagicMock(); response.status_code=http
            response.json.return_value={'result':{'points_count':count}}
            with patch('remediation_rag.requests.get',return_value=response):
                state=status()
            self.assertEqual(state['available'],bool(count))
            self.assertIn('RAG-ACT',state['message'])

    def test_minimal_patch_strategy_does_not_present_bootstrap_as_selected_base(self):
        env=Environment(loader=FileSystemLoader(TEMPLATES),autoescape=True); env.globals['_']=lambda text:text
        html=env.get_template('_remediation_strategy.html').render(item={'strategy':{
            'approach':{'name':'Minimal patches'},'representation':'lossless DOM patch',
            'framework_knowledge':{'framework':'bootstrap','components':[]}}})
        self.assertIn('Minimal patches',html)
        self.assertIn('Original page; no imposed framework',html)
        self.assertNotIn('Bootstrap',html)

    def test_prompts_responses_and_feedback_have_distinct_headings(self):
        env=Environment(loader=FileSystemLoader(TEMPLATES),autoescape=True); env.globals['_']=lambda text:text
        html=env.get_template('_remediation_call_prompts.html').render(item={
            'model_calls':[{'call_number':1,'requested_model':'local/test','stage':'generate','status':'returned',
                            'prompt':'<unsafe>','response':'actual response'}], 'feedback_text':'measured feedback'})
        dom=BeautifulSoup(html,'html.parser')
        self.assertIn('Prompt sent to the model',dom.get_text())
        self.assertIn('Response returned by the model',dom.get_text())
        self.assertIn('feedback after this iteration',dom.get_text())
        self.assertNotIn('<unsafe>',html)

    def test_dataset_panel_order_and_lazy_controls(self):
        env=Environment(loader=FileSystemLoader(TEMPLATES),autoescape=True)
        text=(TEMPLATES/'configuration.html').read_text()
        self.assertLess(text.index('Dynamic-page evaluation protocol'),text.index('Internal dataset'))
        self.assertLess(text.index('Internal dataset'),text.index('Regional settings'))
        self.assertIn('data-lazy-content-control',text)
