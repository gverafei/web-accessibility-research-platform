"""Stored results: URL/slider reuse without rewriting experiment evidence."""
import json
from pathlib import Path

TERMINAL = {'accepted', 'completed_with_warnings', 'failed',
            'metrics_not_achieved', 'review_not_achieved'}


def candidate_path(value):
    path = Path(value).resolve() if value else None
    root = Path('/datasets/remediations').resolve()
    return path if path and root in path.parents and path.is_file() else None


def slider_identity(configuration):
    """Compare experimental controls, not catalogue presentation or RAG flags."""
    if not isinstance(configuration, dict):
        return None
    model = configuration.get('model_configuration')
    level = configuration.get('preservation_level')
    if (not isinstance(model, dict) or not model.get('model')
            or type(level) is not int or level not in range(5)):
        return None
    return model['model'], model.get('reasoning_effort'), level


def reusable_request(cursor, normalized_url, source_id, configuration):
    identity = slider_identity(configuration)
    if identity is None:
        return None
    cursor.execute("""SELECT b.*, r.source_result_id, r.status run_status,
            r.accepted_iteration_id, i.output_path, e.status acquisition_status
        FROM browser_remediation_requests b
        LEFT JOIN remediation_runs r ON r.id=b.remediation_run_id
        LEFT JOIN remediation_iterations i ON i.id=r.accepted_iteration_id AND i.run_id=r.id
        LEFT JOIN experiments e ON e.id=b.acquisition_experiment_id
        WHERE b.normalized_url=%s ORDER BY b.id DESC""", (normalized_url,))
    for item in cursor.fetchall():
        try:
            saved = json.loads(item.get('configuration_json') or 'null')
        except (ValueError, TypeError):
            continue
        if slider_identity(saved) != identity:
            continue
        if not item.get('remediation_run_id'):
            if item.get('acquisition_status') in {'queued', 'running'}:
                return item
            if item.get('acquisition_status') == 'completed' and item.get('status') != 'failed':
                return item
            continue
        if item.get('run_status') in {'queued', 'running'}:
            return item
        if (item.get('run_status') in {'accepted', 'completed_with_warnings'}
                and candidate_path(item.get('output_path'))):
            return item
    return None


def reusable_run(cursor, normalized_url, configuration):
    """Also recover normal runs created outside the browser extension."""
    identity = slider_identity(configuration)
    if identity is None:
        return None
    cursor.execute("""SELECT r.*, i.output_path
        FROM remediation_runs r
        JOIN experiment_results original ON original.id=r.source_result_id
        LEFT JOIN remediation_iterations i ON i.id=r.accepted_iteration_id AND i.run_id=r.id
        WHERE original.normalized_url=%s AND r.status IN
          ('queued','running','accepted','completed_with_warnings')
        ORDER BY r.id DESC""", (normalized_url,))
    priorities = (15, 35, 55, 75, 90)
    for run in cursor.fetchall():
        try:
            model = json.loads(run.get('model_config_json') or 'null')
        except (ValueError, TypeError):
            continue
        if not isinstance(model, dict) or model.get('model') != run.get('generator_model'):
            continue
        if (model.get('model'), model.get('reasoning_effort')) != identity[:2]:
            continue
        if run.get('accessibility_priority') != priorities[identity[2]]:
            continue
        mode = 'regenerate_refine' if identity[2] >= 3 else 'iterative'
        if run.get('execution_mode') != mode:
            continue
        if run['status'] in {'queued', 'running'} or candidate_path(run.get('output_path')):
            return run
    return None


def completion_configuration(run):
    """Describe the recovered run, never the controls used to retrieve it."""
    from remediation_approaches import APPROACHES
    from remediation_model_choices import run_model_presentation
    model = run_model_presentation(run)
    effort = model['reasoning_effort']
    label = model['label'] or run.get('generator_model') or '—'
    if effort:
        label += ' · ' + ('Light' if effort == 'low' else effort.title()) + ' reasoning'
    priorities = (15, 35, 55, 75, 90)
    priority = run.get('accessibility_priority')
    level = priorities.index(priority) if priority in priorities else None
    return {'selectedModel': run.get('generator_model'), 'modelName': label,
            'preservation': level, 'preservationName': APPROACHES[level].name if level is not None else '—',
            'rag': bool(run.get('use_rag')), 'wave': bool(run.get('use_wave'))}



def stored_measurements(cursor, run, iteration_id):
    cursor.execute('SELECT axe_wcag_violations AS axe_violations,lighthouse_score FROM experiment_results WHERE id=%s',
                   (run['source_result_id'],))
    original = cursor.fetchone() or {}
    final = {}
    if iteration_id:
        cursor.execute('SELECT axe_wcag_violations AS axe_violations,lighthouse_score FROM remediation_iterations WHERE id=%s AND run_id=%s',
                       (iteration_id, run['id']))
        final = cursor.fetchone() or {}
    def values(item):
        return {'axe': item.get('axe_violations'), 'lighthouse': item.get('lighthouse_score')}
    return {'original': values(original), 'final': values(final),
            'iteration_id': iteration_id,
            'targets': {'axe': run.get('max_axe'), 'lighthouse': run.get('min_lighthouse')}}
