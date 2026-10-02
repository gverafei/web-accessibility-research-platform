"""Stored extension results: exact configuration reuse and measured comparisons."""
import json
from pathlib import Path

TERMINAL = {'accepted', 'completed_with_warnings', 'failed',
            'metrics_not_achieved', 'review_not_achieved'}


def candidate_path(value):
    path = Path(value).resolve() if value else None
    root = Path('/datasets/remediations').resolve()
    return path if path and root in path.parents and path.is_file() else None


def reusable_request(cursor, normalized_url, source_id, configuration):
    cursor.execute("""SELECT b.*, r.source_result_id, r.status run_status,
            r.accepted_iteration_id, i.output_path, e.status acquisition_status,
            original.experiment_id source_experiment_id
        FROM browser_remediation_requests b
        LEFT JOIN remediation_runs r ON r.id=b.remediation_run_id
        LEFT JOIN remediation_iterations i ON i.id=r.accepted_iteration_id AND i.run_id=r.id
        LEFT JOIN experiments e ON e.id=b.acquisition_experiment_id
        LEFT JOIN experiment_results original ON original.id=%s
        WHERE b.normalized_url=%s ORDER BY b.id DESC""", (source_id, normalized_url))
    for item in cursor.fetchall():
        try:
            saved = json.loads(item.get('configuration_json') or 'null')
        except (ValueError, TypeError):
            continue
        if saved != configuration:
            continue
        if not item.get('remediation_run_id'):
            if source_id is None and item.get('acquisition_status') in {'queued', 'running'}:
                return item
            if (source_id is not None and item.get('acquisition_status') == 'completed'
                    and item.get('source_experiment_id') == item.get('acquisition_experiment_id')):
                return item
            continue
        if item.get('source_result_id') != source_id:
            continue
        if item.get('run_status') in {'queued', 'running'}:
            return item
        if (item.get('run_status') in {'accepted', 'completed_with_warnings'}
                and candidate_path(item.get('output_path'))):
            return item
    return None



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
