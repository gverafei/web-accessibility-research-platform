"""Intervention changes independently from the experimental acceptance contract."""

COMMON_CONDITIONS = {
    "iterations": 3, "lighthouse": 94, "axe": 3, "aim": 9,
    "rag_top_k": 4, "review": "automated",
}


def common_conditions(settings=None):
    """Resolve study targets once; callers persist them with the new run."""
    conditions = dict(COMMON_CONDITIONS)
    for setting, name, upper in (
        ('remediation_min_lighthouse', 'lighthouse', 100),
        ('remediation_max_axe', 'axe', 2147483647),
    ):
        raw = (settings or {}).get(setting, conditions[name])
        try:
            value = int(str(raw).strip())
        except (TypeError, ValueError):
            raise ValueError(f'{setting} must be a whole number.') from None
        if not 0 <= value <= upper:
            raise ValueError(f'{setting} must be between 0 and {upper}.')
        conditions[name] = value
    return conditions


def automatic_recipe(priority, execution_mode="iterative", settings=None):
    conditions = common_conditions(settings)
    if execution_mode == "single_shot":
        return {**conditions, "iterations":1, "temperature":0.20,
                "cost":0.15, "seconds":240, "tier":"low"}
    intervention = {
        15: (0.05, 0.15, 240, "low"),
        35: (0.20, 0.20, 300, "low"),
        55: (0.50, 0.25, 360, "medium"),
        75: (0.50, 0.40, 600, "high"),
        90: (0.50, 0.50, 600, "xhigh"),
    }[priority]
    return {**conditions, **dict(zip(
        ("temperature", "cost", "seconds", "tier"), intervention))}
