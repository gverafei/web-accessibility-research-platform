"""LLM planning grounded in non-overlapping, frozen DOM component identities."""
import json
from bs4 import BeautifulSoup, Tag, Comment


def component_candidates(source):
    soup = BeautifulSoup(source, "html.parser")
    root = soup.body or soup
    candidates = []
    def visit(node, selector):
        if node.name in {"script", "style", "noscript", "template"}: return
        if node.get("id") and len(soup.find_all(id=node["id"]))==1:
            selector="[id="+json.dumps(node["id"])+"]"
        children = [child for child in node.children if isinstance(child, Tag)]
        # Split layout wrappers, never split a functional component blindly.
        functional_classes={'carousel','swiper','swiper-container','slick-slider','modal','dropdown','accordion','tab-content'}
        functional_group=bool(set(node.get('class') or []) & functional_classes) or node.get('role') in {'dialog','menu','menubar','tablist','tree','grid'}
        direct_text=any(str(child).strip() for child in node.children
                        if not isinstance(child,(Tag,Comment)))
        # A layout containing a descendant search form is not itself a form.
        # Split its sibling regions, while preserving actual form/widget roots.
        layout_wrapper=node.name in {'div','main'} and len(node.find_all(True))>80
        if layout_wrapper and len(children)>1 and not functional_group and not direct_text:
            positions = {}
            for child in children:
                positions[child.name] = positions.get(child.name, 0) + 1
                visit(child, selector + f" > {child.name}:nth-of-type({positions[child.name]})")
            return
        if not node.get_text(" ",strip=True) and not node.select("img,video,input,button,svg"): return
        candidates.append({"id":f"c{len(candidates)}", "selector":selector, "source":str(node), "element":node.name,
                           "identity":str(node.get("id") or "") + " " + " ".join(node.get("class", [])),
                           "text":node.get_text(" ",strip=True), "images":len(node.select("img")), "controls":len(node.select("input,button,select,textarea"))})
    positions = {}
    for child in root.children:
        if not isinstance(child, Tag): continue
        positions[child.name] = positions.get(child.name, 0) + 1
        visit(child, f"body > {child.name}:nth-of-type({positions[child.name]})")
    return candidates


def validate_component_plan(proposal, candidates):
    known = {item["id"]:item for item in candidates}
    if not isinstance(proposal, dict):
        raise ValueError('Planner response must be an object')
    assignments = proposal.get("components")
    if not isinstance(assignments, list) or any(not isinstance(item, dict) for item in assignments):
        raise ValueError('Planner components must be an array of objects')
    ids = [item.get("id") for item in assignments]
    if any(not isinstance(identity, str) for identity in ids):
        raise ValueError('Planner component ids must be strings')
    if len(ids) != len(set(ids)) or set(ids) != set(known):
        raise ValueError("Planner must assign every frozen component exactly once; missing/duplicate/invented components rejected")
    for item in assignments:
        if item.get("area") not in ("header","main","footer") or item.get("intervention") not in ("preserve","repair","regenerate"):
            raise ValueError("Planner returned an invalid area or intervention")
        dependencies=item.get('depends_on') or []
        if not isinstance(dependencies,list) or any(not isinstance(dependency,str) for dependency in dependencies):
            raise ValueError('Planner dependencies must be an array of component ids')
        if any(dependency not in known for dependency in dependencies):
            raise ValueError("Planner invented a component dependency")
    # Keep source order, never let the LLM shuffle or manufacture markup.
    by_id = {item["id"]:item for item in assignments}
    return [{**candidate, **{key:by_id[candidate["id"]].get(key) for key in ("area","intervention","reason","root_cause","depends_on")}} for candidate in candidates]


def planning_prompt(candidates, failures, instruction, visual_available=False):
    summaries = [{key:value for key,value in item.items() if key != "source"} for item in candidates]
    prompt = """You are the information-architecture/accessibility planning specialist, not the generator. Inspect the frozen DOM component inventory and measured failures. Assign EVERY component exactly once; do not invent ids, omit menus or merge unrelated tasks. Identify navigation, hero/carousel, article/list, forms, promotional strips and footer by purpose, not merely tag names. Preserve functional groups and explain cross-component CSS/JS dependencies. Select only genuinely defective components for regeneration; retain healthy content. Return JSON {components:[{id,area:header|main|footer,intervention:preserve|repair|regenerate,root_cause,depends_on:[component ids],reason}],rationale}.\n"""
    prompt += ('Original screenshot references are attached; use them alongside the authoritative DOM inventory.\n'
               if visual_available else 'No screenshot is attached. Ground assignments in the DOM inventory and failure evidence only; do not invent visual observations.\n')
    prompt += instruction + "\nComponents: " + json.dumps(summaries,ensure_ascii=False) + "\nFailures: " + json.dumps(failures,ensure_ascii=False)
    if len(prompt) > 180000: raise ValueError("Planner input exceeds context budget; no source inventory was truncated")
    return prompt


def reconstruction_tasks(components):
    return [{"area":item["area"],"key":item["id"],"source":item["source"],"prefix":f"warp-{item['id']}-","selector":item["selector"],"reason":item.get("reason"),"depends_on":item.get("depends_on") or []} for item in components]
