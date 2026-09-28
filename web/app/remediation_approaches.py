"""Versioned intervention policies, independent of model tier and gate scores."""
from dataclasses import dataclass
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class Approach:
    step: int
    name: str
    engine: str
    instruction: str
    reference: str
    max_operations: int


APPROACHES = (
    Approach(1, "Minimal patches", "minimal_patch", "Only attributes, small insertions and narrowly scoped CSS. No element replacement, component substitution or layout restructuring.", "https://arxiv.org/abs/2608.24913", 20),
    Approach(2, "Localized repair", "localized_patch", "Repair individual defective elements. Small semantic replacements are allowed; never replace a whole navigation, section, form or content region.", "https://arxiv.org/html/2507.19549v1", 35),
    Approach(3, "Coordinated repair", "coordinated_patch", "Follow the planner's root-cause groups and dependencies. Coordinate HTML, scoped CSS and local keyboard behavior without redesigning the page or replacing its framework.", "https://arxiv.org/html/2606.21926v1", 60),
    Approach(4, "HTML regeneration", "regenerate_html", "Regenerate the complete page from full acquired HTML using the original whole-document prompt and optional Bootstrap structural reference. Retain the initial one-shot. Refine only with localized patches to the best regenerated page; roll back regressions.", "https://doi.org/10.3390/computers15060343", 35),
    Approach(5, "Markdown regeneration", "regenerate_markdown", "Regenerate the complete page from quality-checked Markdown using the same original whole-document prompt and optional Bootstrap structural reference. Retain the initial one-shot. Refine only with localized patches to the best regenerated page; roll back regressions.", "https://doi.org/10.3390/computers15060343", 35),
)


def approach_for(priority):
    step = next((index for index, threshold in enumerate((15, 35, 55, 75, 100)) if int(priority or 55) <= threshold), 4)
    return APPROACHES[step]


def presentation_priority(priority, strategy=None):
    """Classify known renderer versions without rewriting research history.

    Old protected-block pilots were submitted as step 5 before that engine
    moved to step 4. Their saved configuration remains unchanged.
    """
    if isinstance(strategy,dict):
        contract=strategy.get('born_content_contract') or {}
        version=contract.get('version') if isinstance(contract,dict) else None
        if version=='protected-blocks-v1': return 75
        if version=='protected-data-components-v2': return 90
    return priority


def presentation_name(priority, strategy=None):
    """Preserve historical engine identity when current slider labels change."""
    if isinstance(strategy,dict):
        version=(strategy.get('born_content_contract') or {}).get('version')
        if version=='protected-blocks-v1': return 'Content-preserving recomposition'
        if version=='protected-data-components-v2': return 'Born-accessible'
        regeneration=strategy.get('regeneration') or {}
        if regeneration.get('representation') in {'html','markdown'}:
            return 'HTML regeneration' if regeneration['representation']=='html' else 'Markdown regeneration'
    return approach_for(priority).name


def contrast_foreground(background):
    channels=[int(background[index:index+2],16)/255 for index in (1,3,5)]
    linear=[value/12.92 if value<=.04045 else ((value+.055)/1.055)**2.4 for value in channels]
    luminance=sum(weight*value for weight,value in zip((.2126,.7152,.0722),linear))
    black=(luminance+.05)/.05
    white=1.05/(luminance+.05)
    return '#000000' if black>=white else '#ffffff'


def constrain_plan(document, plan, approach, selected_selectors=(), base_url=None):
    """Enforce intervention scope independently of the model's persona."""
    soup = BeautifulSoup(document, "html.parser")
    accepted, rejected = [], []
    rejected.extend({'operation':operation,'reason':'operation budget exceeded; split remaining targeted repairs across refinements'} for operation in (plan.get('operations') or [])[approach.max_operations:])
    for operation in (plan.get("operations") or [])[:approach.max_operations]:
        invalid_fields = [field for field in ('action','selector','name','tag','html','css','javascript')
                          if field in operation and not isinstance(operation[field], str)]
        if invalid_fields:
            rejected.append({'operation':operation,'reason':'patch fields must be strings: '+', '.join(invalid_fields)})
            continue
        action = operation.get("action")
        selector = str(operation.get("selector") or "")
        reason = None
        if action=='wrap_element' and (approach.step==1 or operation.get('tag') not in {'ul','ol'}):
            reason='only localized or stronger repairs may add native list wrappers'
        if action=="append_javascript" and approach.step<3:
            reason="minimal/localized approaches do not rewrite behavior"
        if action in {"set_attribute","remove_attribute"} and approach.step<=2 and str(operation.get("name") or "").lower() in {"href","src","action","method","name","value","type","onclick","onchange"}:
            reason = "local repairs cannot change task destinations or control contracts"
        if action == "replace_element":
            if approach.step == 1:
                reason = "minimal patches forbid replacement"
            elif approach.step == 2:
                try:
                    nodes = soup.select(selector)
                    if any(node.name in {"nav", "main", "section", "article", "form", "header", "footer"} or len(node.find_all(True)) > 12 for node in nodes):
                        reason = "localized repair cannot replace a region"
                except Exception:
                    reason = "invalid selector"
            if not reason:
                from collections import Counter
                import re
                try:
                    originals=soup.select(selector)
                    replacement=BeautifulSoup(operation.get("html") or "","html.parser")
                    words=lambda node: Counter(re.findall(r"\w+",node.get_text(" ",strip=True).casefold()))
                    from urllib.parse import urljoin
                    resources=lambda node: {(element.name,key,urljoin(base_url or "",element.get(key)) if key!="name" else element.get(key)) for element in [node,*node.find_all(True)] for key in ("href","src","action","name") if element.get(key)}
                    for original in originals:
                        required=words(original)
                        retained=words(replacement)
                        if sum((required-retained).values())>max(1,sum(required.values())*.05): reason="replacement discards source text; keep the previous component"
                        if resources(original)-resources(replacement): reason="replacement discards destinations/assets/control names; keep the previous component"
                except Exception: reason="replacement contract could not be verified"
        if action == "append_css" and approach.step == 1:
            import re
            selectors = re.findall(r"([^{}]+)\{", operation.get("css") or "")
            if any(re.search(r"(^|[,\s])(body|html|\*)(?=[:,\s]|$)", value.strip()) for value in selectors):
                reason = "minimal patches forbid global CSS overrides"
        (rejected if reason else accepted).append({"operation":operation,"reason":reason} if reason else operation)
    return {**plan, "operations":accepted}, rejected
