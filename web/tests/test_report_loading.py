import importlib
import sys
import types
import unittest
from pathlib import Path

from flask import render_template


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

if "database" not in sys.modules:
    database_stub = types.ModuleType("database")
    database_stub.init_db = lambda: None
    database_stub.get_connection = lambda: None
    sys.modules["database"] = database_stub

main = importlib.import_module("main")


class LoadingReportTestCase(unittest.TestCase):
    def test_scatter_styling_is_registered_before_report_charts(self):
        template = (APP_DIR / 'templates' / 'report.html').read_text()
        self.assertIn("filename='js/scatter_visuals.js'", template)
        self.assertLess(template.index('Chart.register(window.warpScatterVisuals)'),
                        template.index('new Chart('))
        styling = (APP_DIR / 'static/js/scatter_visuals.js').read_text()
        self.assertIn("!== 'scatter'", styling)
        self.assertIn('dataset.pointBorderWidth = 1', styling)
        self.assertIn("axeLighthouseChart: '#103b72'", styling)
        self.assertIn("domAxeChart: '#7654a3'", styling)
        self.assertNotIn('rgba(', styling)
        self.assertNotIn('dataset.data =', styling)
        self.assertNotIn('chart.options.scales', styling)

    def test_slow_report_navigation_uses_lightweight_loading_page(self):
        listing = (APP_DIR / 'templates' / 'experiments.html').read_text()
        loading = (APP_DIR / 'templates' / 'report_transition.html').read_text()
        route = (APP_DIR / 'routes' / 'experiments.py').read_text()
        self.assertIn("url_for('experiments.experiment_report_loading'", listing)
        self.assertIn('warpAutoReload(5000', listing)
        self.assertIn('class="loading-status-card"', loading)
        self.assertIn('window.location.replace', loading)
        self.assertIn('def experiment_report_loading(experiment_id):', route)

    def test_evaluation_list_has_no_llm_usage_controls_or_costs(self):
        listing = (APP_DIR / 'templates' / 'experiments.html').read_text()
        route = (APP_DIR / 'routes' / 'experiments.py').read_text()
        self.assertNotIn('summary.llm_experiments', listing)
        self.assertNotIn('summary.llm_tokens', listing)
        self.assertNotIn('experiment.include_semantic', listing)
        self.assertNotIn('experiment.llm_tokens', listing)
        self.assertNotIn('WAVE and LLM combined', listing)
        self.assertNotIn('AS llm_tokens', route[route.index('def experiments():'):route.index('all_experiments = cursor.fetchall()')])

    def test_list_deletions_use_shared_in_place_handler(self):
        for name in ('experiments.html', 'remediation_history.html'):
            template = (APP_DIR / 'templates' / name).read_text()
            self.assertIn('data-list-delete', template)
            self.assertIn('data-delete-error=', template)
        handler = (APP_DIR / 'static/js/list_delete.js').read_text()
        self.assertIn("cache: 'no-store'", handler)
        self.assertIn('currentSummary.replaceWith(summary)', handler)
        self.assertIn('window.warpAlert', handler)
        self.assertNotIn('location.reload', handler)

    def test_evaluation_list_matches_restrained_remediation_data_style(self):
        from bs4 import BeautifulSoup
        dom=BeautifulSoup((APP_DIR/'templates'/'experiments.html').read_text(),'html.parser')
        table=dom.select_one('.evaluation-history-table')
        self.assertIsNotNone(table)
        self.assertFalse(table.select('tbody strong'))
        self.assertIsNotNone(table.select_one('.evaluation-cost small'))
        self.assertIsNotNone(table.select_one('tr[data-row-open]'))
        self.assertEqual(len(table.select('thead th')),6)
        self.assertEqual([cell.get_text(strip=True) for cell in table.select('thead th')[:5]],
                         ['{{ _("Evaluation") }}','{{ _("Progress") }}','{{ _("Acquisition") }}','{{ _("Tools") }}','{{ _("Cost and time") }}'])
        self.assertIsNone(table.select_one('.experiment-title-edit'))
        self.assertIsNotNone(table.select_one('.evaluation-source-chip'))
        self.assertIsNotNone(table.select_one('.evaluation-tool-chip'))
        self.assertIsNotNone(table.select_one('.evaluation-progress-line'))
        self.assertIn('evaluation_history.css',(APP_DIR/'templates'/'base.html').read_text())

    def test_research_lists_expose_stable_row_identifiers(self):
        evaluations=(APP_DIR/'templates'/'experiments.html').read_text()
        comparisons=(APP_DIR/'templates'/'comparisons.html').read_text()
        detail=(APP_DIR/'templates'/'comparison_detail.html').read_text()
        self.assertIn('#{{ experiment.id }}',evaluations)
        self.assertIn('#{{ study.id }}',comparisons)
        self.assertIn('#{{ result.id }}',comparisons)
        identifier='#{{ member.source_remediation_run_id or member.source_result_id or member.id }}'
        self.assertIn(identifier,comparisons)
        self.assertIn(identifier,detail)

    def test_research_list_filters_are_instant_and_local(self):
        evaluations=(APP_DIR/'templates'/'experiments.html').read_text()
        remediations=(APP_DIR/'templates'/'remediation_history.html').read_text()
        comparisons=(APP_DIR/'templates'/'comparisons.html').read_text()
        styles=(APP_DIR/'static'/'css'/'style.css').read_text()
        self.assertIn('id="evaluationListFilter"',evaluations)
        self.assertIn("evaluationFilter.addEventListener('input'",evaluations)
        self.assertIn('id="remediationListFilter"',remediations)
        self.assertIn("remediationFilter.addEventListener('input'",remediations)
        self.assertIn("pageFilter.addEventListener('input'",comparisons)
        self.assertIn("event=>event.preventDefault()",comparisons)
        self.assertIn('.comparison-source-controls>button[type="submit"]{display:none}',styles)
        self.assertIn('class="list-filter-control"',evaluations)
        self.assertIn('class="list-filter-control"',remediations)
        self.assertIn('.list-filter-control svg{position:absolute;top:50%;right:.7rem;width:1.2rem',styles)

    def test_dashboard_separates_costs_and_exposes_descriptive_insights(self):
        route=(APP_DIR/'routes'/'experiments.py').read_text()
        template=(APP_DIR/'templates'/'dashboard.html').read_text()
        styles=(APP_DIR/'static'/'css'/'style.css').read_text()
        self.assertIn('"evaluation":evaluation_cost',route)
        self.assertIn('"remediation":remediation_cost',route)
        self.assertIn('"total":evaluation_cost+remediation_cost',route)
        self.assertIn('generator_model model,COUNT(*) uses',route)
        self.assertIn('removed_per_dollar',route)
        self.assertIn('reduction_percent',route)
        self.assertIn('{{ _("Most-used LLM") }}',template)
        self.assertIn('{{ _("Most-used preservation strategy") }}',template)
        self.assertIn('{{ _("Best observed Axe reduction per dollar") }}',template)
        self.assertIn('{{ _("Best observed Axe reducer") }}',template)
        self.assertIn('{{ _("cost excluded; not a causal ranking") }}',template)
        self.assertIn('based on %(count)s retained runs',template)
        self.assertNotIn('n={{ insights.',template)
        self.assertIn('{{ _("not a causal ranking") }}',template)
        self.assertIn('<span>#{{ item.id }}</span>',template)
        self.assertNotIn('<span>✦</span>',template)
        self.assertIn('.dashboard-metrics .research-metric>strong{font-size:1.42rem;overflow-wrap:anywhere}',styles)

    def test_evaluation_and_comparison_headers_share_identity_pattern(self):
        report=(APP_DIR/'templates'/'report.html').read_text()
        comparison=(APP_DIR/'templates'/'comparison_detail.html').read_text()
        remediation=(APP_DIR/'templates'/'_remediation_report_header.html').read_text()
        styles=(APP_DIR/'static'/'css'/'style.css').read_text()
        self.assertIn('{{ _("Evaluation") }} #{{ experiment.id }}',report)
        self.assertIn('class="report-hero-meta">{{ experiment.created_at }}',report)
        self.assertNotIn('{{ _("Reproducible web accessibility evaluation") }}',report)
        self.assertNotIn('{{ _("Navigate") }}',report)
        self.assertIn('class="comparison-hero-meta">{{ study.created_at }}',comparison)
        self.assertIn('.report-hero-meta,.comparison-hero-meta',styles)
        self.assertIn("<small>{{ _('Started') }} {{ run.created_at }}</small>",remediation)
        self.assertIn(
            '.report-hero h1,.comparison-hero h1{max-width:none;margin:.15rem 0;font-size:1.75rem;font-weight:500;line-height:1.2;letter-spacing:normal}',
            styles,
        )

    def test_evaluation_pause_actions_have_spacing_and_visible_names(self):
        listing=(APP_DIR/'templates'/'experiments.html').read_text()
        report=(APP_DIR/'templates'/'report.html').read_text()
        history_styles=(APP_DIR/'static'/'css'/'evaluation_history.css').read_text()
        self.assertIn('class="evaluation-delete-form"',listing)
        self.assertIn('.evaluation-delete-form{margin-left:.35rem}',history_styles)
        self.assertIn("<span>{{ _('Pause') }}</span>",report)
        self.assertIn("<span>{{ _('Resume') }}</span>",report)
        self.assertNotIn('experiment-action-pause icon-only-action',report)
        self.assertNotIn('experiment-action-resume icon-only-action',report)

    def test_running_experiment_renders_skeleton_instead_of_report_charts(self):
        experiment = {
            "id": 21,
            "title": "Queued study",
            "status": "running",
            "urls": "https://a.example\nhttps://b.example",
            "include_wave": True,
            "include_semantic": True,
        }
        with main.app.test_request_context("/experiments/21"):
            html = render_template(
                "report.html",
                experiment=experiment,
                results=[{"url": "https://a.example", "status": "completed"}],
            )

        self.assertIn("loading-report", html)
        self.assertIn('aria-valuenow="50.0"', html)
        self.assertNotIn('id="axeLighthouseChart"', html)
        self.assertNotIn("new Chart", html)

    def test_report_defines_sortable_measurement_matrix(self):
        template = (APP_DIR / "templates" / "report.html").read_text(encoding="utf-8")

        self.assertIn('id="measurementTable"', template)
        self.assertIn('("Axe issues"), "axe_total"', template)
        self.assertIn('("Failed rules"), "axe_failed_rules"', template)
        self.assertIn('("Needs review"), "axe_needs_review"', template)
        self.assertIn('("AIM", "wave_aim")', template)
        self.assertIn('("LLM findings"), "llm_total"', template)
        self.assertIn("if(rank)rank.textContent=index+1", template)
        self.assertIn('data-column="wave_aim"', template)
        self.assertIn('const extraColumns=', template)
        self.assertIn('studyOverview.after(measurementMatrix)', template)
        self.assertIn('"llm_tokens"', template)
        self.assertIn('"wave_credits"', template)
        self.assertIn('appendColumn("total_cost"', template)
        self.assertIn('moveToEnd("runtime")', template)
        self.assertIn('moveAfter("axe_best_practice","axe_total")', template)
        self.assertIn('moveAfter("axe_failed_rules","axe_minor")', template)
        self.assertIn('moveAfter("axe_needs_review","axe_failed_rules")', template)
        self.assertIn(".column-axe_failed_rules", template)
        self.assertIn('const attachPagination=', template)
        self.assertIn('document.getElementById("compositePriorityTable")', template)
        self.assertIn('document.getElementById("url-results")', template)

    def test_full_study_overview_uses_three_by_three_desktop_grid(self):
        stylesheet = (APP_DIR / "static" / "css" / "style.css").read_text(encoding="utf-8")

        self.assertIn("metric-grid:has(>article:nth-child(9))", stylesheet)
        self.assertIn("grid-template-columns:repeat(3,minmax(0,1fr))", stylesheet)

    def test_cross_tool_table_uses_only_the_active_ranking_metrics(self):
        template = (APP_DIR / "templates" / "report.html").read_text(encoding="utf-8")

        self.assertIn('if analysis.ranking_mode == "composite"', template)
        self.assertIn('if analysis.ranking_mode == "unavailable"', template)
        self.assertIn("At least three pages", template)
        self.assertIn("at least n = 3", template)

    def test_report_adds_axe_lighthouse_evidence_when_wave_is_not_selected(self):
        template = (APP_DIR / "templates" / "report.html").read_text(encoding="utf-8")

        self.assertIn('id="criticalLighthouseChart"', template)
        self.assertIn('id="axeLighthouseDisagreementChart"', template)
        self.assertIn('id="lighthouseProfileChart"', template)
        self.assertIn("axe_critical_lighthouse", template)
        self.assertIn('id="lighthouseProfileChart"', template)

    def test_research_configuration_separates_installation_defaults(self):
        configuration = (APP_DIR / "templates" / "configuration.html").read_text(encoding="utf-8")
        index = (APP_DIR / "templates" / "index.html").read_text(encoding="utf-8")

        self.assertIn('name="axe_standard"', configuration)
        self.assertIn('name="axe_include_best_practices"', configuration)
        self.assertIn("Show Axe Best Practices in reports", configuration)
        self.assertIn('name="openrouter_api_key"', configuration)
        self.assertIn('name="wave_api_key"', configuration)
        self.assertIn('name="wave_report_type" value="2"', configuration)
        self.assertNotIn('<select class="form-select" id="wave_report_type"', configuration)
        self.assertIn('name="app_timezone"', configuration)
        self.assertNotIn('name="ui_theme"', configuration)
        self.assertIn('name="show_axe_densities"', configuration)
        self.assertIn("timezone_groups", configuration)
        self.assertIn('name="enable_lazy_load_scroll"', configuration)
        self.assertIn("Dynamic-page evaluation protocol", configuration)
        self.assertIn("Regional settings", configuration)
        self.assertNotIn("DB_HOST", configuration)
        self.assertNotIn('("mistral_model","Mistral model")', configuration)
        self.assertIn('name="confirmation_text"', configuration)
        self.assertIn("clear_experiments_phrase", configuration)
        self.assertNotIn('name="axe_standard"', index)

    def test_about_link_is_discreetly_placed_in_footer(self):
        base = (APP_DIR / "templates" / "base.html").read_text(encoding="utf-8")
        about = (APP_DIR / "templates" / "about.html").read_text(encoding="utf-8")

        self.assertIn('<footer class="app-footer">', base)
        self.assertIn("Guillermo Vera-Amaro", about)
        self.assertIn("gvera@uv.mx", about)

if __name__ == "__main__":
    unittest.main()
