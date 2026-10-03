"""Read-only explanations for persisted runtime evidence; not runtime contracts."""
import json
import math
import re
from pathlib import Path

SKILL_COPY = {
    'grounded-accessibility-diagnosis': 'Grounds diagnosis in the current DOM and measured Axe/Lighthouse findings.',
    'minimal-preservation-repair': 'Constrains repairs to small changes while preserving source content and behavior.',
    'coordinated-component-repair': 'Coordinates related components using source order and ownership.',
    'html-born-accessible-regeneration': 'Regenerates a full page from acquired HTML and the selected design base.',
    'markdown-born-accessible-regeneration': 'Regenerates a full page from Markdown and the authoritative UI inventory.',
    'adaptive-evidence-grounding': 'Supplies matching RAG-ACT example pairs during refinement.',
    'measured-evaluation-and-rollback': 'Measures candidates and deterministically retains the best evaluated result.',
}
EVENT_COPY = {
    'acquire': ('Software tool', 'Loads the frozen acquisition.'),
    'transform': ('Software tool', 'Prepares the page representation and content inventory.'),
    'markdown': ('Software tool', 'Transforms acquired content into Markdown.'),
    'prompt': ('Software coordinator', 'Assembles instructions and measured feedback for the next call.'),
    'generate': ('LLM stage', 'Requests candidate generation and records its progress.'),
    'planning': ('LLM stage', 'Requests a model plan for grounded components and dependencies.'),
    'planning_response': ('LLM response', 'Persists the returned planning response before validation.'),
    'patch_diagnosis': ('LLM response', 'Records the conditional model diagnosis and its measured usage.'),
    'evaluate': ('Software tool', 'Runs Axe, Lighthouse and the configured optional evaluators.'),
    'metrics': ('Software tool', 'Records measured evaluator and preservation results.'),
    'rag_retrieval': ('Software tool', 'Searches the local RAG-ACT example corpus.'),
    'rag_deferred': ('Software coordinator', 'Records why RAG-ACT retrieval was not used.'),
    'patch': ('Software tool', 'Validates and applies constrained model-proposed operations.'),
    'reconstruction': ('Software tool', 'Assembles the model proposal under source-content contracts.'),
    'invalid_output': ('Software validator', 'Rejects unusable output after recording the actual model call.'),
    'decision': ('Software coordinator', 'Applies the frozen acceptance policy to measured evidence.'),
    'rollback': ('Software coordinator', 'Keeps the best measured candidate after a regression.'),
    'complete': ('Software coordinator', 'Finalizes the run and retains its evaluated result.'),
    'skills_activated': ('Software coordinator', 'Selects versioned procedures and their allowed typed tools.'),
    'plan_validated': ('Software validator', 'Checks component ownership, completeness and source order in the proposed plan.'),
    'patch_diagnosis_skipped': ('Software coordinator', 'Records why no additional model diagnosis was requested.'),
    'budget_stop': ('Software coordinator', 'Stops additional work under the frozen budget.'),
    'plateau_stop': ('Software coordinator', 'Stops refinement after measured improvement has plateaued.'),
    'marginal_stop': ('Software coordinator', 'Stops when measured improvement does not justify another call.'),
    'refine': ('Software coordinator', 'Schedules localized refinement using measured preservation findings.'),
    'evaluation_retry': ('Software tool', 'Retries an incomplete evaluator response without generating a new candidate.'),
    'evaluation_failed': ('Software tool', 'Records the evaluator failure without fabricating measurements.'),
    'widget_replay_normalization': ('Software tool', 'Prepares recognized captured widgets for replay with their frozen data.'),
    'resources_retained': ('Software tool', 'Restores omitted source resources under the content contract.'),
    'no_op': ('Software validator', 'Records an unchanged candidate after validating the proposed operations.'),
    'area_checkpoints': ('Software coordinator', 'Keeps measured area checkpoints for subsequent candidate assembly.'),
    'widget_replay_warning': ('Software validator', 'Records replay limitations detected in captured dynamic controls.'),
    'refinement_interrupted': ('Software coordinator', 'Records an interruption while preserving the best evaluated candidate.'),
    'failed': ('Software coordinator', 'Records a run failure and its original diagnostic evidence.'),
    'accepted': ('Software coordinator', 'Records candidate acceptance under the configured policy.'),
    'extraction_quality': ('Software validator', 'Checks the frozen network and rendered source views for acquisition completeness.'),
    'patch_source_selection': ('Software function', 'Selects the frozen source view used for localized repairs.'),
    'source_hydration': ('Software function', 'Restores captured images in static placeholders from the frozen rendered source.'),
    'unmatched_lighthouse_nodes': ('Software function', 'Records Lighthouse findings that could not be mapped to source elements.'),
}


def load_model_calls(strategy, run_id, dataset_root):
    """Only this run's evidence may be read; never reconstruct absent prompts."""
    path = (strategy.get('model_call_evidence') or {}).get('path')
    if not path:
        return []
    root = (Path(dataset_root) / 'remediations' / str(run_id)).resolve()
    candidate = Path(path).resolve()
    if root not in candidate.parents or candidate.name != 'model-call-evidence.json':
        return []
    try:
        document = json.loads(candidate.read_text(encoding='utf-8'))
        calls = document.get('calls', [])
        return [call for call in calls if isinstance(call, dict)] if isinstance(calls, list) else []
    except (OSError, ValueError, AttributeError):
        return []


def iteration_presentation(item, run_id, dataset_root):
    strategy = item.get('strategy') or {}
    item['retention_summary'] = retention_summary(strategy.get('content_retention'))
    visual = (strategy.get('candidate_selection') or {}).get('visual_similarity_percent')
    item['visual_similarity_percent'] = visual if (
        isinstance(visual, (int, float)) and not isinstance(visual, bool)
        and math.isfinite(visual) and 0 <= visual <= 100) else None
    runtime = strategy.get('agentic_runtime') or {}
    contracts = {row['name']: row for row in runtime.get('tool_contracts', []) if isinstance(row, dict) and row.get('name')}
    item['runtime_skills'] = [dict(row, description=SKILL_COPY.get(row.get('id'),
        'Executes a recorded versioned procedure; consult its technical evidence for the contract.'))
        for row in runtime.get('iteration_skills', []) if isinstance(row, dict)]
    item['runtime_tools'] = [dict(row, description=(contracts.get(row.get('tool')) or {}).get('description') or
        'Executes the recorded typed software operation; not a model call.')
        for row in runtime.get('tool_invocations', []) if isinstance(row, dict)]
    item['model_calls'] = load_model_calls(strategy, run_id, dataset_root)
    item['pipeline_stages'] = []
    for name, evidence in (strategy.get('stage_accounting') or {}).items():
        calls = evidence.get('llm_calls')
        cost = evidence.get('cost_usd')
        if calls == 0 and not float(evidence.get('seconds') or 0) and not float(cost or 0) and name in {'planning', 'diagnosis'}:
            continue
        kind = 'LLM calls' if calls else ('External evaluator' if name == 'automated_evaluation' and float(cost or 0) else 'Software tool')
        item['pipeline_stages'].append(dict(evidence, name=name, kind=kind))


def retention_summary(evidence):
    """Read-only, equally weighted UI summary; never an acceptance/ranking gate."""
    evidence = evidence if isinstance(evidence, dict) else {}
    definitions = (
        ('Words', 'original_words', 'candidate_words', 'text_percent'),
        ('Links', 'original_links', 'candidate_links', 'links_percent'),
        ('Images', 'original_images', 'candidate_images', 'images_percent'),
        ('Banners and media', 'dynamic_images_required', 'dynamic_images_retained', 'dynamic_images_percent'),
    )
    rows, percentages = [], []
    for label, source, candidate, metric in definitions:
        value = evidence.get(metric)
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 100
        if valid:
            percentages.append(value)
        rows.append({'label':label, 'source':evidence.get(source),
                     'candidate':evidence.get(candidate), 'percent':value if valid else None})
    return {'percent':round(sum(percentages)/len(percentages),2) if percentages else None,
            'measures':len(percentages), 'rows':rows}


def event_presentation(event):
    try:
        details = event.get('details_json') or {}
        if isinstance(details, str):
            details = json.loads(details)
        if not isinstance(details, dict):
            details = {}
    except (ValueError, TypeError):
        details = {}
    kind, description = EVENT_COPY.get(event.get('event_type'),
        ('Software activity', 'Records a pipeline operation.'))
    category, label = {
        'LLM stage': ('llm', 'LLM'), 'LLM response': ('llm', 'LLM'),
        'Software tool': ('tool', 'Tool'), 'External evaluator': ('tool', 'Tool'),
        'Software coordinator': ('control', 'Control'),
        'Software validator': ('validation', 'Validation'),
        'Software function': ('function', 'Function'),
    }.get(kind, ('function', 'Function'))
    message = event.get('message') or ''
    if event.get('actor') == 'Acceptance coordinator':
        # Display only: keep frozen feedback and the original event intact.
        message = re.split(r'\b(?:Axe failures|Measured Axe failures|Lighthouse accessibility failures|Automated preservation evidence)\s*:',
                           message, maxsplit=1, flags=re.IGNORECASE)[0].rstrip()
        message = message.split('Refine the preceding candidate using the exact evidence below.', 1)[0].rstrip(' :\n')
    event.update(activity_kind=kind, activity_description=description,
                 activity_category=category, activity_label=label,
                 activity_message=message,
                 activity_model=details.get('model') if kind.startswith('LLM') else None)
