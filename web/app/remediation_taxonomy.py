"""Reporting helpers for the Fathallah et al. AccessGuru taxonomy."""

import json
from pathlib import Path


LAYOUT_RULES = {
    "meta-viewport", "meta-viewport-large", "color-contrast",
    "avoid-inline-spacing", "target-size", "frame-title",
    "color-contrast-enhanced",
}

SYNTACTIC_RULES = {
    "blink", "scope-attr-valid", "aria-allowed-attr", "aria-allowed-role",
    "aria-valid-attr", "aria-valid-attr-value", "autocomplete-valid",
    "role-img-alt", "td-headers-attr", "area-alt", "object-alt", "svg-img-alt",
    "input-image-alt", "image-alt", "html-lang-valid", "html-xml-lang-mismatch",
    "duplicate-id-aria", "tabindex", "valid-lang", "aria-required-attr",
    "aria-required-parent", "aria-required-children", "aria-deprecated-role",
    "presentation-role-conflict", "aria-prohibited-attr", "list",
    "frame-focusable-content", "meta-refresh", "marquee", "skip-link",
    "landmark-no-duplicate-contentinfo", "landmark-contentinfo-is-top-level",
    "landmark-one-main", "landmark-unique", "landmark-banner-is-top-level",
    "landmark-complementary-is-top-level", "landmark-main-is-top-level",
    "landmark-no-duplicate-main", "landmark-no-duplicate-banner", "document-title",
    "label", "label-title-only", "summary-name", "definition-list", "dlitem",
    "th-has-data-cells", "empty-table-header", "empty-heading", "listitem",
    "image-redundant-alt", "link-name", "link-in-text-block", "input-button-name",
    "aria-text", "aria-tooltip-name", "aria-command-name", "aria-input-field-name",
    "aria-meter-name", "aria-progressbar-name", "aria-dialog-name",
    "aria-toggle-field-name", "aria-hidden-body", "aria-hidden-focus",
    "nested-interactive", "scrollable-region-focusable", "no-autoplay-audio",
    "region", "frame-tested", "frame-title-unique", "video-caption", "heading-order",
    "accesskeys", "page-has-heading-one", "bypass", "server-side-image-map",
    "button-name", "aria-roledescription", "aria-roles", "duplicate-id",
    "duplicate-id-active", "html-has-lang", "select-name",
}


def category_for_rule(rule_id):
    if rule_id in LAYOUT_RULES:
        return "Layout"
    if rule_id in SYNTACTIC_RULES:
        return "Syntactic"
    return "Unclassified"


def axe_taxonomy(raw_path):
    """Count affected elements (not only distinct rules) per category."""
    result = {name: {"count": 0, "rules": []} for name in ("Syntactic", "Layout", "Unclassified")}
    path = Path(raw_path or "")
    if not path.is_file():
        return result
    try:
        violations = json.loads(path.read_text(encoding="utf-8"))["violations"]
    except (OSError, ValueError, KeyError, TypeError):
        return result
    for violation in violations:
        rule_id = str(violation.get("id") or "unknown")
        category = category_for_rule(rule_id)
        instances = max(1, len(violation.get("nodes") or []))
        result[category]["count"] += instances
        result[category]["rules"].append({"rule": rule_id, "instances": instances,
            "impact": violation.get("impact"), "help": violation.get("help")})
    return result
