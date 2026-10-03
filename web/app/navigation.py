"""Logical application breadcrumbs: no database queries or resource fetching."""
from flask import request, url_for
from flask_babel import gettext as _


def breadcrumbs():
    endpoint = request.endpoint
    args = request.view_args or {}
    simple = {
        'experiments.index': _('Dashboard'),
        'experiments.new_acquisition': _('New acquisition'),
        'experiments.configuration': _('Configuration'),
        'experiments.experiments': _('Evaluations'),
        'experiments.manage_urls': _('Manage URLs'),
        'experiments.compose_experiment': _('Combine evaluations'),
        'experiments.import_experiment_json': _('Import'),
        'comparisons.comparisons': _('Comparisons'),
        'remediation.runs': _('Remediation runs'),
        'remediation.new_run': _('New remediation'),
        'remediation.templates': _('Templates'),
    }
    trail = []
    if endpoint in simple:
        trail.append({'label': simple[endpoint]})
    elif endpoint in ('experiments.experiment_report',
                      'experiments.experiment_report_loading',
                      'experiments.manage_experiment_urls'):
        trail.append({'label': _('Evaluations'), 'url': url_for('experiments.experiments')})
        report = {'label': _('Evaluation #%(id)s', id=args['experiment_id'])}
        if endpoint == 'experiments.manage_experiment_urls':
            report['url'] = url_for('experiments.experiment_report_loading',
                                    experiment_id=args['experiment_id'])
        trail.append(report)
        if endpoint == 'experiments.manage_experiment_urls':
            trail.append({'label': _('Manage URLs')})
    elif endpoint == 'remediation.run_detail':
        trail.extend([{'label': _('Remediation runs'), 'url': url_for('remediation.runs')},
                      {'label': _('Remediation #%(id)s', id=args['run_id'])}])
    elif endpoint == 'comparisons.comparison_detail':
        trail.extend([{'label': _('Comparisons'), 'url': url_for('comparisons.comparisons')},
                      {'label': _('Comparison #%(id)s', id=args['comparison_id'])}])
    elif endpoint == 'rag_maintenance.examples':
        root = {'label': _('RAG-ACT')}
        if args.get('identity'):
            root['url'] = url_for('rag_maintenance.examples', **{
                key: request.args[key] for key in ('q', 'source', 'outcome', 'size', 'page', 'collection')
                if key in request.args})
        trail.append(root)
        if args.get('identity'):
            trail.append({'label': _('Example')})
    else:
        # Error pages still show a way home; unknown routes never invent a parent.
        trail.append({'label': _('Page')})
    return trail
