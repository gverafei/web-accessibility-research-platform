"""Keep research target attainment separate from result availability."""


def measurable_noop(patch_result):
    """An explicit empty patch may be measured; rejected operations may not.

    Measurement, not an LLM's assertion, decides whether an unchanged page
    meets the configured targets. Never turn malformed/skipped plans into it.
    """
    return (isinstance(patch_result, dict) and patch_result.get('applied') == []
            and patch_result.get('skipped') == [])


def achieved_feedback(axe_findings, lighthouse_findings):
    rules=', '.join(str(item.get('rule') or item.get('id') or 'unclassified') for item in axe_findings) or 'none reported'
    return ('Automated targets achieved; this does not certify absence of accessibility barriers. '
            f'Remaining Axe rules: {rules}. Lighthouse audit findings: {len(lighthouse_findings)}.')


def completion_status(accepted, evaluated_count, review_policy, targets_achieved):
    if accepted:
        return 'accepted'
    if not evaluated_count:
        return 'failed'
    if review_policy == 'automated':
        return 'completed_with_warnings'
    return 'review_not_achieved' if targets_achieved else 'metrics_not_achieved'


def retain_interrupted_result(best_evaluated_iteration, review_policy, provider_failure):
    """Only retain committed measured results; never bypass specialist review."""
    return bool(best_evaluated_iteration and review_policy == 'automated' and provider_failure)
