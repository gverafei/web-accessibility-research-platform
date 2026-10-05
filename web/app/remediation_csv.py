"""Read-only tabular export of recorded remediation measurements."""
import csv
from io import StringIO
import json

from axe_metrics import project_wcag
from remediation_report_presentation import retention_summary


RUN_FIELDS = (
    'id', 'title', 'status', 'source_result_id', 'created_at', 'completed_at',
    'execution_mode', 'accessibility_priority', 'transformation_format',
    'generator_provider', 'generator_model', 'reviewer_provider', 'reviewer_model',
    'temperature', 'use_rag', 'use_wave', 'max_iterations', 'max_cost_usd',
    'max_execution_seconds', 'min_lighthouse', 'max_axe', 'min_aim',
    'accepted_iteration_id', 'total_input_tokens', 'total_output_tokens',
    'total_cost_usd', 'execution_seconds', 'progress_message', 'error_message',
)
MEASUREMENT_FIELDS = (
    'axe_issue_instances', 'axe_best_practice_issues', 'lighthouse_score',
    'wave_aim_score', 'dom_distance_percent', 'content_retention_percent',
    'text_retention_percent', 'links_retention_percent', 'images_retention_percent',
    'visual_similarity_percent',
)
FIELDS = tuple('run_' + name for name in RUN_FIELDS) + (
    'source_experiment_id', 'source_url', 'source_name', 'source_evaluated_at',
    'imported', 'row_kind', 'iteration_id', 'iteration_number', 'is_retained',
    'measured_at', 'decision', 'decision_reason', 'generator_provider',
    'generator_model', 'reviewer_provider', 'reviewer_model',
) + MEASUREMENT_FIELDS + (
    'input_tokens', 'output_tokens', 'cost_usd', 'execution_seconds',
    'rag_used', 'rag_example_count', 'evidence_recovered',
)


def _object(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return value if isinstance(value, dict) else {}


def _cell(value):
    # Titles, URLs and diagnostic text are untrusted even in stored evidence.
    if isinstance(value, str) and (value.startswith(('\t', '\r', '\n')) or
                                  value.lstrip().startswith(('=', '+', '-', '@'))):
        return "'" + value
    return value


def remediation_csv(run, source, iterations):
    """Original plus each stored iteration; no source or candidate mutation."""
    strategies = [_object(item.get('strategy_json')) for item in iterations]
    common = {'run_' + name: run.get(name) for name in RUN_FIELDS}
    common.update(source_experiment_id=source.get('experiment_id'),
                  source_url=source.get('url'),
                  source_name=source.get('display_name') or source.get('page_title') or source.get('url'),
                  source_evaluated_at=source.get('evaluated_at'),
                  imported=bool(run.get('import_provenance_json')))
    if any(strategy.get('recovery') for strategy in strategies):
        common.update(run_total_input_tokens=None, run_total_output_tokens=None)

    original = project_wcag(source)
    rows = [dict(common, row_kind='original', is_retained=False,
                 measured_at=source.get('evaluated_at'),
                 axe_issue_instances=original.get('axe_violations'),
                 axe_best_practice_issues=original.get('axe_best_practice_issues'),
                 lighthouse_score=original.get('lighthouse_score'),
                 wave_aim_score=original.get('wave_aim_score'))]
    for stored, strategy in zip(iterations, strategies):
        item = project_wcag(stored)
        recovery = bool(strategy.get('recovery'))
        retention = _object(strategy.get('content_retention'))
        selection = _object(strategy.get('candidate_selection'))
        rag = _object(strategy.get('rag'))
        retrieved = rag.get('retrieved')
        count = len(retrieved) if isinstance(retrieved, list) else None
        row = dict(common, row_kind='iteration', iteration_id=item.get('id'),
                   iteration_number=item.get('iteration_number'),
                   is_retained=(item.get('id') == run['accepted_iteration_id']
                                if run.get('accepted_iteration_id') is not None else None),
                   measured_at=item.get('created_at'), decision=item.get('decision'),
                   decision_reason=item.get('decision_reason'),
                   axe_issue_instances=item.get('axe_violations'),
                   axe_best_practice_issues=item.get('axe_best_practice_issues'),
                   lighthouse_score=item.get('lighthouse_score'),
                   wave_aim_score=item.get('wave_aim_score'),
                   dom_distance_percent=item.get('dom_distance'),
                   content_retention_percent=retention_summary(retention)['percent'],
                   text_retention_percent=retention.get('text_percent'),
                   links_retention_percent=retention.get('links_percent'),
                   images_retention_percent=retention.get('images_percent'),
                   visual_similarity_percent=selection.get('visual_similarity_percent'),
                   rag_used=bool(count) if count is not None else None,
                   rag_example_count=count, evidence_recovered=recovery)
        for name in ('generator_provider', 'generator_model', 'reviewer_provider', 'reviewer_model',
                     'input_tokens', 'output_tokens', 'cost_usd', 'execution_seconds'):
            row[name] = None if recovery and name in {
                'input_tokens', 'output_tokens', 'cost_usd', 'execution_seconds'} else item.get(name)
        rows.append(row)

    output = StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows({key: _cell(value) for key, value in row.items()} for row in rows)
    return '\ufeff' + output.getvalue()
