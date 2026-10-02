import html as html_lib
import base64
import io
import json
import os
import re
import time
import traceback
import uuid
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from remediation_completion import completion_status, achieved_feedback, retain_interrupted_result, measurable_noop
from remediation_selection import candidate_rank, rollback_feedback, POLICY as SELECTION_POLICY
from remediation_diagnosis import diagnosis_needed, diagnosis_prompt, grounded_diagnosis
from remediation_adaptive import rag_activation, meaningful_improvement
from born_content import content_manifest, manifest_context, bind_content, layout_only, coherent_regions
from born_composition import COMPOSITION_INSTRUCTION
from vera_regeneration import MODES as REGENERATION_MODES, generation_messages, generation_evidence, complete_candidate, omission_context, resource_omissions, task_omissions, preservation_refinement_needed
from born_framework import framework_assets, embed_framework, framework_evidence
from bs4 import BeautifulSoup
from PIL import Image, ImageChops, ImageStat

from database import get_connection
from axe_metrics import POLICY as AXE_COUNTING_POLICY, candidate_metrics, persist_metrics
from framework_knowledge import retrieve_framework_knowledge
from regeneration_references import selected_framework, DESIGN_BASES
from regeneration_components import component_instruction
from reconstruction_agents import regenerate_areas, ReconstructionBudgetStop
from reconstruction_regression import checkpoint_areas
from remediation_approaches import APPROACHES, approach_for, constrain_plan
from remediation_model_policy import reasoning_effort
from remediation_model_choices import model_choice
from remediation_outputs import parse_json_response
from remediation_planner import component_candidates, planning_prompt, validate_component_plan, reconstruction_tasks
from remediation_extraction import extraction_quality, markdown_representation, markdown_quality
from remediation_baseline import baseline_prompt, baseline_candidate
from remediation_content_contract import preserve_resources, hydrate_static_placeholders, original_page_wrapper, prepare_frozen_widget_replay, captured_widget_replay_warnings, select_captured_patch_source, grounded_lighthouse_context
from frozen_carousel_replay import replay_manifest
from remediation_rag import retrieval_evidence, adaptive_example_limit
from remediation_rag import prompt_context as rag_prompt_context, retrieval_query as rag_retrieval_query, retrieve as rag_retrieve
from remediation_taxonomy import axe_taxonomy
from remediation_agent_runtime import AgentRuntime
from remediation_call_evidence import RecordedModelCalls
from remediation_tool_registry import ToolContract
from settings import evaluator_runtime_config, get_settings


DATASET_ROOT=Path(os.getenv("DATASET_ROOT","/datasets"))
EVALUATOR_HTTP_TIMEOUT_SECONDS=240


def ensure_remediation_resource_policy():
    root=DATASET_ROOT/"remediations"
    root.mkdir(parents=True,exist_ok=True)
    metadata=root/".warp-dataset.json"
    expected={"resource_policy":"external","purpose":"remediation candidates"}
    if not metadata.is_file() or metadata.read_text(encoding="utf-8",errors="replace") != json.dumps(expected,sort_keys=True):
        metadata.write_text(json.dumps(expected,sort_keys=True),encoding="utf-8")


class _DomSequence(HTMLParser):
    def __init__(self): super().__init__(convert_charrefs=True); self.tokens=[]
    def handle_starttag(self, tag, attrs):
        semantic={key:value for key,value in attrs if key in {"role","type","aria-label","aria-labelledby","aria-describedby","aria-live","alt","for","name"}}
        self.tokens.append(f"<{tag}:{sorted(semantic.items())}>")
    def handle_startendtag(self, tag, attrs): self.handle_starttag(tag,attrs)
    def handle_endtag(self, tag): self.tokens.append(f"</{tag}>")


def dom_distance(original, candidate):
    left=_DomSequence(); right=_DomSequence(); left.feed(original); right.feed(candidate)
    similarity=SequenceMatcher(None,left.tokens,right.tokens,autojunk=False).ratio()
    return round((1-similarity)*100,2),len(left.tokens),len(right.tokens)


class _DomInventory(HTMLParser):
    def __init__(self): super().__init__(convert_charrefs=True); self.tags=Counter(); self.accessibility=Counter()
    def handle_starttag(self,tag,attrs):
        self.tags[tag]+=1
        for key,value in attrs:
            if key in {"role","alt","lang","for"} or key.startswith("aria-"):
                self.accessibility[key]+=1
    def handle_startendtag(self,tag,attrs): self.handle_starttag(tag,attrs)


def dom_change_summary(original,candidate):
    before=_DomInventory(); after=_DomInventory(); before.feed(original); after.feed(candidate)
    added=[{"element":key,"count":value} for key,value in sorted((after.tags-before.tags).items()) if value]
    removed=[{"element":key,"count":value} for key,value in sorted((before.tags-after.tags).items()) if value]
    accessibility=[{"attribute":key,"count":value} for key,value in sorted((after.accessibility-before.accessibility).items()) if value]
    return {"elements_added":added,"elements_removed":removed,"accessibility_attributes_added":accessibility}


class _ContentInventory(HTMLParser):
    """Inventory durable page meaning without treating CSS or markup as content."""
    def __init__(self, base_url=None):
        super().__init__(convert_charrefs=True); self.hidden=0; self.words=Counter(); self.links=Counter(); self.images=Counter(); self.base_url=base_url
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if tag in {"script","style","noscript","svg"}: self.hidden+=1
        if tag == "a":
            href=(values.get("href") or "").strip()
            if href and not href.startswith(("#","javascript:")):
                self.links[urljoin(self.base_url,href) if self.base_url else href]+=1
        if tag == "img":
            src=(values.get("src") or values.get("data-src") or values.get("data-original") or "").strip()
            if src and not src.startswith("data:"):
                self.images[urljoin(self.base_url,src) if self.base_url else src]+=1
    def handle_startendtag(self,tag,attrs): self.handle_starttag(tag,attrs)
    def handle_endtag(self,tag):
        if tag in {"script","style","noscript","svg"} and self.hidden: self.hidden-=1
    def handle_data(self,data):
        if not self.hidden: self.words.update(re.findall(r"[\w.-]+",data.casefold()))


def content_retention(original,candidate,base_url=None):
    before=_ContentInventory(base_url); after=_ContentInventory(base_url); before.feed(original); after.feed(candidate)
    word_total=sum(before.words.values()); link_total=sum(before.links.values())
    # Repeated responsive/desktop instances of the same asset are one piece of
    # information. Count unique source URLs so removing duplication is not
    # incorrectly reported as image loss.
    original_image_urls=set(before.images); candidate_image_urls=set(after.images); image_total=len(original_image_urls)
    original_destinations=set(before.links); candidate_destinations=set(after.links)
    word_kept=sum((before.words & after.words).values()); link_kept=len(original_destinations & candidate_destinations); image_kept=len(original_image_urls & candidate_image_urls)
    return {
        "text_percent":round(100*word_kept/max(1,word_total),2),
        "links_percent":round(100*link_kept/max(1,len(original_destinations)),2) if original_destinations else 100.0,
        "link_measurement":"unique original destinations; responsive duplicates count once",
        "original_link_destinations":len(original_destinations),"candidate_link_destinations":len(candidate_destinations),
        "images_percent":round(100*image_kept/max(1,image_total),2) if image_total else 100.0,
        "original_words":word_total,"candidate_words":sum(after.words.values()),
        "original_links":link_total,"candidate_links":sum(after.links.values()),
        "original_images":image_total,"candidate_images":len(candidate_image_urls),
        "missing_text_examples":[word for word,count in (before.words-after.words).most_common(12) for _ in range(min(count,2))],
        "missing_link_examples":sorted(original_destinations-candidate_destinations)[:12],
        "missing_image_examples":sorted(original_image_urls-candidate_image_urls)[:12],
    }


def reconstruction_inventory(source, base_url=None):
    """Extract page meaning and UI anatomy independently from its presentation."""
    soup=BeautifulSoup(source,"html.parser")
    for node in soup.select("script,style,noscript,template,svg"): node.decompose()
    def text(node,limit=500): return " ".join(node.get_text(" ",strip=True).split())[:limit]
    inventory={
        "document_text":soup.get_text(" ",strip=True),
        "reading_order":[{"element":item.name,"text":text(item,10000)} for item in soup.select("h1,h2,h3,h4,h5,h6,p,li,dt,dd,caption,th,td,label,legend,summary") if text(item)],
        "title":text(soup.title) if soup.title else "",
        "language":(soup.html or {}).get("lang") if soup.html else None,
        "headings":[{"level":int(item.name[1]),"text":text(item)} for item in soup.select("h1,h2,h3,h4,h5,h6")[:120]],
        "links":[{"text":text(item,240),"url":urljoin(base_url,item.get("href"))} for item in soup.select("a[href]")],
        "images":[{"url":urljoin(base_url,item.get("src") or item.get("data-src") or ""),"alt":item.get("alt"),"title":item.get("title"),"context":text(item.parent,500)} for item in soup.select("img[src],img[data-src]")],
        "controls":[{"element":item.name,"type":item.get("type"),"name":item.get("name"),"label":item.get("aria-label") or item.get("title") or text(item,180)} for item in soup.select("button,input,select,textarea")],
        "sections":[{"element":item.name,"label":item.get("aria-label") or item.get("id"),"text":text(item,1200)} for item in soup.select("header,nav,main,section,article,aside,footer")[:100]],
        "signals":[item.name for item in soup.find_all(True)[:2000]],
    }
    inventory["forms"]=[{"action":urljoin(base_url,item.get("action") or base_url or ""),"method":item.get("method","get"),"id":item.get("id")} for item in soup.select("form")]
    for control,item in zip(inventory["controls"],soup.select("button,input,select,textarea")):
        label=soup.find("label",attrs={"for":item.get("id")}) if item.get("id") else None
        label=label or item.find_parent("label")
        control.update({"id":item.get("id"),"value":item.get("value"),"required":item.has_attr("required"),"label":text(label) if label else control["label"],"options":[{"value":option.get("value"),"text":text(option)} for option in item.select("option")]})
    # Sliders commonly keep their current/queued images in inline JavaScript or
    # style attributes instead of <img>. They remain acquired evidence, not
    # permission to crawl: expose only URLs already present in the frozen DOM.
    asset_pattern=r'''(?i)(?:https?:)?//[^\s"'<>\\]+?\.(?:png|jpe?g|webp|gif|svg)(?:\?[^\s"'<>\\]*)?'''
    css_assets=re.findall(r'''(?i)url\(\s*["']?([^\s"')]+)''',source)
    inventory["media_assets"]=sorted({urljoin(base_url,item) for item in re.findall(asset_pattern,source)+css_assets if not item.startswith("data:") and re.search(r"(?i)\.(?:png|jpe?g|webp|gif|svg)(?:[?#]|$)",item)})
    classes=" ".join(" ".join(item.get("class") or []) for item in soup.find_all(True)[:2000])
    inventory["signals"].extend(re.findall(r"[a-zA-Z][\w-]+",classes))
    return inventory


def serialize_reconstruction_inventory(inventory, limit=180000, fragmented=False):
    """Keep complete content at its actual whole-page or per-area delivery scope."""
    if fragmented:
        # The coordinator keeps the complete inventory; each area receives its
        # own complete extraction. Do not impose a whole-page LLM context limit
        # on the independently bounded, fragment-based route.
        return json.dumps({'mode':'fragmented','title':inventory.get('title'),
            'language':inventory.get('language'),
            'delivery':'Complete assigned inventories sent separately to area agents; no global content truncation.',
            'counts':{key:len(inventory.get(key) or []) for key in ('reading_order','links','images','forms','controls')}},ensure_ascii=False)
    serialized=json.dumps(inventory,ensure_ascii=False)
    if len(serialized)>limit:
        raise ValueError(f"The complete reconstruction inventory exceeds the {limit}-character context budget. No truncated page was submitted; use localized repair for this page.")
    return serialized


def generator_failure_evidence(evidence, mode):
    """Ablate Axe's suggested fixes without changing localization or execution."""
    if mode=="independent": return []
    if mode!="localized": return evidence
    return [{"rule":item.get("rule"),"nodes":[{"target":node.get("target"),"html":node.get("html")} for node in item.get("nodes") or []]} for item in evidence or []]


def observed_document_media(source, base_url=None):
    """DOM-observed media, not image-like strings buried in scripts or CSS files."""
    soup=BeautifulSoup(source,"html.parser"); assets=set()
    for item in soup.select("img[src],img[data-src],video[poster]"):
        value=item.get("src") or item.get("data-src") or item.get("poster")
        if value and not value.startswith("data:"): assets.add(urljoin(base_url,value))
    for item in soup.select("[style]"):
        for value in re.findall(r'''(?i)url\(\s*["']?([^\s"')]+)''',item.get("style","")):
            if not value.startswith("data:"): assets.add(urljoin(base_url,value))
    return assets


def rendered_media_retention(source, candidate, base_url=None):
    required=observed_document_media(source,base_url); retained=required & observed_document_media(candidate,base_url)
    return {"dynamic_images_required":len(required),"dynamic_images_retained":len(retained),
            "dynamic_images_percent":round(100*len(retained)/len(required),2) if required else 100.0,
            "media_measurement":"DOM-observed URLs after browser evaluation; not a successful-download or visual-quality score"}


def standalone_reconstruction(candidate, base_url):
    """Absolute assets with local skip/disclosure links, without a foreign base."""
    candidate=absolutize_resources(candidate,base_url)
    candidate=re.sub(r'(?is)<base\b[^>]*>',"",candidate)
    def anchor(match):
        value=match.group(2)
        if "#" in value and value.split("#",1)[0]==(base_url or "").split("#",1)[0]:
            value="#"+value.split("#",1)[1]
        return f'href={match.group(1)}{value}{match.group(1)}'
    return re.sub(r'''(?i)href\s*=\s*(["'])(.*?)\1''',anchor,candidate)


def screenshot_message(path):
    """Return a bounded visual reference suitable for a multimodal chat message."""
    if not path or not Path(path).is_file(): return None
    try:
        with Image.open(path) as image:
            image=image.convert("RGB"); image.thumbnail((1280,1280))
            buffer=io.BytesIO(); image.save(buffer,format="JPEG",quality=72,optimize=True)
    except (OSError,ValueError,Image.DecompressionBombError):
        return None
    return {"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+base64.b64encode(buffer.getvalue()).decode("ascii")}}


def screenshot_references(path):
    """A page overview plus bounded readable top/middle/bottom samples.

    Samples are not component crops; their positional context is explicit.
    The full content contract remains authoritative for unsampled areas.
    """
    overview=screenshot_message(path)
    if not overview: return []
    references=[overview]
    try:
        with Image.open(path) as original:
            if original.height<=original.width*1.5: return references
            height=min(original.height,1200)
            for label,top in [('top',0),('middle',(original.height-height)//2),('bottom',original.height-height)]:
                crop=original.crop((0,top,original.width,top+height)).convert('RGB')
                crop.thumbnail((1280,1280))
                buffer=io.BytesIO(); crop.save(buffer,format='JPEG',quality=72,optimize=True)
                references.extend([{'type':'text','text':f'Original page readable {label} sample; vertical offset {top}px. This is context, not the complete content inventory.'},
                                   {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(buffer.getvalue()).decode('ascii')}}])
    except (OSError,ValueError,Image.DecompressionBombError):
        return references
    return references


def complete_html_response(value):
    value=value.strip()
    value=re.sub(r"^```(?:html)?\s*|\s*```$","",value,flags=re.I)
    match=re.search(r"(?is)(<!doctype\s+html.*|<html\b.*)</html>",value)
    return match.group(0) if match else value


def preservation_instruction(priority):
    if priority <= 15:
        return "Patch the acquired HTML conservatively. Preserve its CSS, layout, visual identity, content, links, controls, and behavior; change only what is needed to remove measured accessibility barriers."
    if priority <= 35:
        return "Prioritize recognizable visual and behavioral fidelity while allowing small semantic and contrast corrections. Preserve every piece of content, destination, control, and task."
    if priority <= 55:
        return "Balance the recognizable design with accessibility. Structural changes are allowed when needed, but preserve all content, destinations, controls, tasks, and reading order."
    if priority <= 75:
        return "Prioritize accessibility and screen-reader clarity over pixel-level fidelity. You may simplify layout and styling, but preserve all content, destinations, controls, tasks, and meaningful media."
    return "Build a screen-reader-first, keyboard-complete version. Visual resemblance is not required and decorative styling may be removed. Never omit, summarize, merge, or invent content, links, data rows, controls, tasks, or meaningful media."


def absolutize_resources(html, base_url):
    """Resolve candidate resources against the acquired page's canonical base URL."""
    if not base_url: return html
    from bs4 import BeautifulSoup
    def resolve(value):
        value=value.strip()
        if not value or value.startswith(("#","data:","mailto:","tel:","javascript:","blob:")): return value
        return urljoin(base_url,value)
    def resolve_srcset(value):
        if 'data:' in value.lower():
            return value
        entries=[]
        for part in value.split(','):
            tokens=part.split()
            if tokens:
                entries.append(f"{resolve(tokens[0])} {' '.join(tokens[1:])}".rstrip())
        return ', '.join(entries)
    # Work on attribute values: rewriting quotes in serialized HTML corrupts
    # inline CSS, and global replacement also alters application script text.
    def resolve_css(css):
        pattern = r'''(?i)url\(\s*(?:"([^"]*)"|'([^']*)'|([^\s)'" ][^)]*))\s*\)'''
        def replacement(match):
            value = next(value for value in match.groups() if value is not None).strip()
            resolved = resolve(value).replace('\\', '\\\\').replace('"', '\\"')
            return f'url("{resolved}")'
        return re.sub(pattern, replacement, css)
    soup = BeautifulSoup(html, 'html.parser')
    for node in soup.find_all(True):
        for attr in ('src','href','action','poster','data-src','data-original'):
            if isinstance(node.get(attr), str): node[attr] = resolve(node[attr])
        for attr in ('srcset','data-srcset'):
            if isinstance(node.get(attr), str): node[attr] = resolve_srcset(node[attr])
        if node.name == 'img':
            lazy = node.get('data-src') or node.get('data-original')
            if lazy and (not node.get('src') or node['src'].startswith('data:')):
                node['src'] = lazy
        if isinstance(node.get('style'), str): node['style'] = resolve_css(node['style'])
        if node.name == 'style' and node.string is not None:
            node.string.replace_with(resolve_css(str(node.string)))
    return str(soup)


def document_base_url(source, fallback):
    match=re.search(r'(?i)<base\b[^>]*href\s*=\s*["\']([^"\']+)',source)
    if not match: return fallback
    declared=match.group(1).strip()
    resolved=urljoin(fallback,declared) if fallback else declared
    return resolved if urlparse(resolved).scheme in {"http","https"} else fallback


def _now(settings): return datetime.now(ZoneInfo(settings["app_timezone"])).replace(tzinfo=None)


def _bounded_progress(message):
    """Fit human progress text to the persisted VARCHAR contract."""
    return str(message or "")[:500]


def _event(cursor,conn,run_id,actor,event_type,message,details=None):
    cursor.execute("INSERT INTO remediation_events (run_id,actor,event_type,message,details_json,created_at) VALUES (%s,%s,%s,%s,%s,%s)",(run_id,actor,event_type,message[:1000],json.dumps(details) if details else None,_now(get_settings())))
    conn.commit()


def _progress(cursor, conn, run_id, phase, percent, message, iteration=0, status="running"):
    cursor.execute(
        """UPDATE remediation_runs SET status=%s,current_phase=%s,current_iteration=%s,
        progress_percent=%s,progress_message=%s,progress_updated_at=%s WHERE id=%s""",
        (status, phase, iteration, max(0, min(100, percent)), _bounded_progress(message), _now(get_settings()), run_id),
    )
    _event(cursor,conn,run_id,{"acquire":"Acquisition","transform":"Transformer","prompt":"Prompt planner","generate":"Generator","evaluate":"Evaluation team","complete":"Coordinator"}.get(phase,"System"),phase,message,{"iteration":iteration,"progress_percent":max(0,min(100,percent))})


def _snapshot(run):
    if run.get("response_source_path") and Path(run["response_source_path"]).is_file(): return Path(run["response_source_path"])
    if run.get("source_snapshot_path") and Path(run["source_snapshot_path"]).is_file(): return Path(run["source_snapshot_path"])
    if run.get("storage_key") and run.get("relative_path"):
        path=DATASET_ROOT/run["storage_key"]/run["relative_path"]
        if path.is_file(): return path
    return None


def compact_html(source, limit=240000):
    """Remove non-remediation payload before applying a final safety limit."""
    source=re.sub(r"(?s)<!--.*?-->","",source)
    source=re.sub(
        r"(?is)<script\b([^>]*)>.*?</script>",
        lambda match: f"<script{match.group(1)}></script>" if re.search(r"(?i)\bsrc\s*=",match.group(1)) else "",
        source,
    )
    source=re.sub(r"(?is)<(style|noscript)\b.*?>.*?</\1>","",source)
    source=re.sub(r"(?is)<svg\b([^>]*)>.*?</svg>",lambda match:f"<svg{match.group(1)}></svg>",source)
    source=re.sub(r">\s+<","><",source)
    source=re.sub(r"[ \t]{2,}"," ",source)
    return source[:limit]


def lighthouse_failure_evidence(raw_path, limit=8):
    """Return only actionable failed Lighthouse accessibility audits."""
    path=Path(raw_path or "")
    if not path.is_file(): return []
    try: audits=(json.loads(path.read_text(encoding="utf-8")) or {}).get("audits") or {}
    except (OSError,ValueError,TypeError): return []
    failures=[]
    for audit_id,audit in audits.items():
        score=audit.get("score")
        if audit.get("scoreDisplayMode") in {"notApplicable","manual","informative"} or score is None or score >= 1: continue
        items=((audit.get("details") or {}).get("items") or [])[:4]
        failures.append({"audit":audit_id,"title":audit.get("title"),"description":audit.get("description"),"score":score,"items":[{"selector":item.get("node",{}).get("selector"),"snippet":item.get("node",{}).get("snippet"),"explanation":item.get("node",{}).get("explanation")} for item in items]})
    failures.sort(key=lambda item:(item["score"],item["audit"]))
    return failures[:limit]


def repair_context(source, axe_evidence, lighthouse_evidence, limit=50000):
    """Build focused context while keeping the complete document out of the prompt."""
    soup=BeautifulSoup(source,"html.parser")
    head=str(soup.head or "")[:18000]
    nodes=[]
    selectors=[]
    for violation in axe_evidence or []:
        for node in violation.get("nodes") or []:
            target=node.get("target") or []
            selector=target[0] if isinstance(target,list) and target else target if isinstance(target,str) else None
            if selector: selectors.append(selector)
    for audit in lighthouse_evidence or []:
        selectors.extend(item.get("selector") for item in audit.get("items") or [] if item.get("selector"))
    for selector in selectors[:24]:
        try: matches=soup.select(selector)
        except Exception: matches=[]
        for match in matches[:2]:
            parent=match.parent
            nodes.append({"selector":selector,"html":str(match)[:2500],"parent":{"element":parent.name,"id":parent.get('id'),"classes":parent.get('class',[]),"child_elements":[child.name for child in parent.find_all(recursive=False)][:40]},"previous_sibling":str(match.find_previous_sibling() or '')[:600],"next_sibling":str(match.find_next_sibling() or '')[:600]})
    containers=[]
    for node in soup.select('main,article,section,body > div,body > header,body > footer,div[id]'):
        text=node.get_text(' ',strip=True)
        if not text and not node.select('img,iframe,video,input,button'): continue
        identity=node.get('id')
        if identity and len(soup.find_all(id=identity))==1:
            selector='[id='+json.dumps(identity)+']'
        else:
            classes=node.get('class',[])
            selector=node.name+''.join('.'+value for value in classes if re.match(r'^[a-zA-Z_][\w-]*$',value))
            if selector==node.name or len(soup.select(selector))!=1: continue
        containers.append({'selector':selector,'element':node.name,'role':node.get('role'),
                           'words':len(text.split()),'text_start':text[:160],
                           'images':len(node.select('img')),'iframes':len(node.select('iframe')),
                           'controls':len(node.select('input,button,select,textarea'))})
    payload={"document_head":head,"affected_nodes":nodes,"document_size":len(source),
             "substantive_container_candidates":containers[:40],
             "independent_page_overview":compact_html(source,18000)}
    # Bound context without cutting a JSON string mid-object. Explicitly report
    # omitted context; execution still patches the full frozen document.
    payload['context_nodes_omitted']=0
    while len(json.dumps(payload,ensure_ascii=False))>limit and payload['affected_nodes']:
        payload['affected_nodes'].pop(); payload['context_nodes_omitted']+=1
    if len(json.dumps(payload,ensure_ascii=False))>limit:
        payload['independent_page_overview']='Context allowance exceeded; focused nodes unavailable'
        payload['document_head']=head[:max(0,limit//2)]
        while len(json.dumps(payload,ensure_ascii=False))>limit and payload['substantive_container_candidates']:
            payload['substantive_container_candidates'].pop()
    return json.dumps(payload,ensure_ascii=False)


def template_pattern_context(template_html, template_name, axe_evidence):
    """Expose relevant component patterns, never a replacement page skeleton."""
    if not template_html: return "No catalog pattern selected. Preserve the native page framework."
    rules={item.get("rule") for item in axe_evidence or []}
    wanted=[]
    if rules & {"label","select-name","button-name","aria-required-attr"}: wanted.extend(["form","button"])
    if rules & {"landmark-one-main","region","bypass"}: wanted.extend(["nav","main","header"])
    if rules & {"image-alt","svg-img-alt"}: wanted.extend(["figure","img"])
    if not wanted: wanted=["main"]
    soup=BeautifulSoup(template_html,"html.parser"); snippets=[]
    for tag in wanted:
        item=soup.find(tag)
        if item: snippets.append(str(item)[:3000])
    return (f"Catalog component reference: {template_name}. Borrow only applicable semantics or focus patterns; "
            "do not replace the page, its framework, content, or visual identity.\n"+"\n".join(snippets))[:8000]


def apply_repair_plan(document, plan):
    """Apply a constrained selector-based patch plan to the complete frozen HTML."""
    soup=BeautifulSoup(document,"html.parser"); applied=[]; skipped=[]
    operations=plan.get("operations") if isinstance(plan,dict) else None
    for operation in (operations or [])[:60]:
        action=str(operation.get("action") or ""); selector=str(operation.get("selector") or "").strip()
        try: targets=soup.select(selector) if selector else []
        except Exception as error:
            skipped.append({"operation":operation,"reason":f"invalid selector: {error}"}); continue
        if action in {"append_css","append_head_html","append_body_html"}:
            targets=[soup]
        if not targets:
            skipped.append({"operation":operation,"reason":"selector did not match"}); continue
        try:
            if action in {'replace_element','insert_before','insert_after','append_head_html','append_body_html'}:
                markup=str(operation.get('html') or '')
                if re.search(r"(?is)<\s*(script|style)\b|\son[a-z]+\s*=|javascript\s*:",markup):
                    raise ValueError('executable markup is forbidden; use scoped CSS/behavior operations')
                if action!='replace_element' and BeautifulSoup(markup,'html.parser').select('main,[role="main"]'):
                    raise ValueError('inserting a new main does not wrap existing content; use a substantive existing container, never a main placeholder')
            if action == "set_attribute":
                name=str(operation.get("name") or "").strip(); value=str(operation.get("value") or "")
                if not name or re.search(r"[^a-zA-Z0-9_:-]",name): raise ValueError("invalid attribute")
                if name.lower()=="role" and value.lower()=="presentation" and any(target.name=="li" for target in targets):
                    raise ValueError("role=presentation cannot repair an orphan list item; restore list structure")
                if name.lower()=="role" and value.lower()=="main":
                    if any(target.name=="body" or (not target.get_text(" ",strip=True) and len(target.find_all(True))<2) for target in targets):
                        raise ValueError("main landmark must be a substantive page-content container, never body or an empty placeholder")
                for target in targets: target[name]=value
            elif action == "remove_attribute":
                name=str(operation.get("name") or "").strip()
                for target in targets: target.attrs.pop(name,None)
            elif action == "replace_element":
                if selector.lower() in {"html","head","body"}: raise ValueError("root replacement is forbidden")
                raw_markup=str(operation.get("html") or "")
                replacement=BeautifulSoup(raw_markup,"html.parser")
                if not replacement.contents: raise ValueError("empty replacement")
                for target in targets: target.replace_with(BeautifulSoup(str(replacement),"html.parser"))
            elif action == 'wrap_element':
                tag=operation.get('tag')
                if tag not in {'ul','ol'} or any(target.name!='li' for target in targets):
                    raise ValueError('list repair wraps only li elements in ul/ol')
                for target in targets:
                    if target.parent.name in {'ul','ol'}: continue
                    wrapper=soup.new_tag(tag)
                    parent=target.parent
                    navigation_classes={'nav','navbar-nav','pagination','breadcrumb'}
                    if parent.name=='nav' or target.find_parent('nav') or navigation_classes.intersection(parent.get('class') or []):
                        # A native wrapper must not introduce browser-default
                        # bullets/padding into an originally unbulleted menu.
                        # Explicit list semantics survive list-style:none.
                        wrapper['role']='list'
                        wrapper['data-warp-navigation-list']='true'
                        wrapper['style']='list-style: none; margin: 0; padding: 0;'
                    target.wrap(wrapper)
            elif action in {"insert_before","insert_after"}:
                markup=str(operation.get("html") or "")
                for target in targets:
                    fragment=BeautifulSoup(markup,"html.parser")
                    target.insert_before(fragment) if action=="insert_before" else target.insert_after(fragment)
            elif action == "append_css":
                style=soup.new_tag("style"); style["data-warp-repair"]="true"; style.string=str(operation.get("css") or "")[:30000]
                (soup.head or soup).append(style)
            elif action == "append_javascript":
                javascript=str(operation.get("javascript") or "")
                if re.search(r"\b(fetch|XMLHttpRequest|eval|Function|localStorage|sessionStorage)\b|document\.(cookie|write)|(?:window\.)?location\s*=",javascript):
                    raise ValueError("behavior repair must be local; navigation/network/storage/dynamic execution forbidden")
                script=soup.new_tag("script"); script["data-warp-repair"]="true"; script.string=javascript[:30000]
                (soup.body or soup).append(script)
            elif action in {"append_head_html","append_body_html"}:
                markup=str(operation.get("html") or "")
                destination=soup.head if action=="append_head_html" else soup.body
                if destination is None: raise ValueError("document section missing")
                destination.append(BeautifulSoup(markup,"html.parser"))
            else: raise ValueError("unsupported action")
            applied.append(operation)
        except Exception as error: skipped.append({"operation":operation,"reason":str(error)})
    return str(soup),{"applied":applied,"skipped":skipped}


def apply_deterministic_repairs(document, axe_evidence, lighthouse_evidence):
    """Apply narrow, reproducible fixes for measured mechanical failures."""
    soup=BeautifulSoup(document,"html.parser"); applied=[]; seen=set()
    def targets(selector):
        try: return soup.select(selector)
        except Exception: return []
    for failure in axe_evidence or []:
        rule=failure.get("rule")
        for node in failure.get("nodes") or []:
            selector=(node.get("target") or [None])[0]
            if not selector: continue
            for target in targets(selector):
                key=(rule,selector,id(target))
                if key in seen: continue
                seen.add(key)
                if rule=="aria-allowed-role" and target.name=="body" and target.get("role"):
                    target.attrs.pop("role",None); applied.append({"rule":rule,"selector":selector,"repair":"removed invalid body role"})
                elif rule=="presentation-role-conflict" and target.get("role") in {"presentation","none"}:
                    target.attrs.pop("role",None)
                    applied.append({"rule":rule,"selector":selector,"repair":"removed presentational role that conflicted with retained semantics"})
                elif rule=="aria-progressbar-name" and target.get("role")=="progressbar":
                    label=(target.get("title") or target.get("aria-valuetext") or "Progress").strip()
                    target["aria-label"]=label
                    applied.append({"rule":rule,"selector":selector,"repair":"named measured progress indicator from retained metadata"})
                elif rule=="aria-required-children" and target.get("role") and target.name in {"ul","ol","nav","select","table"}:
                    target.attrs.pop("role",None)
                    applied.append({"rule":rule,"selector":selector,"repair":"restored native container semantics instead of incomplete explicit ARIA"})
                elif rule=="link-name" and target.name=="a" and not target.get_text(" ",strip=True) and not target.get("aria-label"):
                    image=target.find("img",alt=True)
                    label=(target.get("title") or (image.get("alt") if image else "") or "").strip()
                    href=str(target.get("href") or "").strip()
                    if not label and href and not href.startswith(("#","javascript:")):
                        parsed=urlparse(href)
                        destination=parsed.hostname or parsed.path.rstrip("/").rsplit("/",1)[-1]
                        if destination: label=f"Link to {destination}"
                    if label:
                        target["aria-label"]=label
                        applied.append({"rule":rule,"selector":selector,"repair":"named empty link from its retained title, image alternative or destination"})
                elif rule=="color-contrast":
                    failure_text=str(node.get("failure") or "")
                    background=re.search(r"background color:\s*(#[0-9a-fA-F]{6})",failure_text)
                    if not background: continue
                    from remediation_approaches import contrast_foreground
                    color=contrast_foreground(background.group(1))
                    style=str(target.get("style") or "")
                    style=re.sub(r"(?i)(^|;)\s*color\s*:[^;]*",r"\1",style).strip(" ;")
                    computed=node.get('computed_style') or {}
                    opacity=1
                    try: opacity=float(computed.get('opacity',1))
                    except (TypeError,ValueError): pass
                    if opacity<1:
                        style=re.sub(r"(?i)(^|;)\s*opacity\s*:[^;]*",r"\1",style).strip(" ;")
                        style=(style+"; " if style else "")+'opacity: 1 !important'
                    target["style"]=(style+"; " if style else "")+f"color: {color} !important;"
                    applied.append({"rule":rule,"selector":selector,"repair":f"selected foreground {color} against measured opaque background {background.group(1)}; browser must re-evaluate"})
    for audit in lighthouse_evidence or []:
        if audit.get("audit")!="label-content-name-mismatch": continue
        for item in audit.get("items") or []:
            selector=item.get("selector")
            for target in targets(selector):
                if target.get_text(" ",strip=True) and target.has_attr("aria-label"):
                    target.attrs.pop("aria-label",None)
                    applied.append({"rule":"label-content-name-mismatch","selector":selector,"repair":"used visible label as accessible name"})
    return str(soup),applied




def call_model(settings, model, prompt, json_mode=False, temperature=None, cost_tier=None, allowed_models=None, messages=None, reasoning_override=None, output_token_limit=None):
    started=time.monotonic()
    if settings.get('_local_llm_config') and not model.startswith('ollama/'):
        raise ValueError('A local run cannot invoke a remote LLM. No cloud fallback is allowed.')
    if model.startswith('ollama/'):
        from local_llm import local_configuration, local_chat
        config = settings.get('_local_llm_config') or local_configuration(settings)
        if not config or model != 'ollama/' + config['model']:
            raise ValueError('The configured Ollama model does not match this run. No cloud fallback is allowed.')
        token_limit = int(os.getenv('REMEDIATION_OUTPUT_TOKEN_LIMIT', '8000' if json_mode else '32000'))
        if output_token_limit is not None:
            token_limit = min(token_limit, output_token_limit)
        content, incoming, outgoing = local_chat(config,
            messages or [{'role': 'user', 'content': prompt}], json_mode,
            temperature, token_limit)
        return content, incoming, outgoing, 0., time.monotonic() - started, model
    if model.startswith('openrouter/'):
        raise ValueError('Automatic model routing has been removed. Select an explicit model.')
    # A complete page still needs a generous output allowance, but an explicit
    # ceiling makes pilot cost bounded and prevents a malformed response from
    # generating indefinitely.
    payload={"model":model,"messages":messages or [{"role":"user","content":prompt}],"max_tokens":int(os.getenv("REMEDIATION_OUTPUT_TOKEN_LIMIT","8000" if json_mode else "32000"))}
    if output_token_limit is not None: payload['max_tokens']=min(payload['max_tokens'],output_token_limit)
    if json_mode: payload["response_format"]={"type":"json_object"}
    configuration = settings.get('_model_configuration') or {}
    if temperature is not None and (configuration.get('model') != model or configuration.get('temperature_supported', True)):
        payload["temperature"]=temperature
    if configuration.get('model') == model and isinstance(configuration.get('max_completion_tokens'), int) and configuration['max_completion_tokens'] > 0:
        payload['max_tokens'] = min(payload['max_tokens'], configuration['max_completion_tokens'])
    effort = (configuration.get('reasoning_effort') if configuration.get('model') == model
              else reasoning_override if reasoning_override is not None else reasoning_effort(model,cost_tier))
    if effort:
        payload["reasoning"]={"effort":effort,"exclude":True}
    response=requests.post(settings["openrouter_base_url"].rstrip("/")+"/chat/completions",headers={"Authorization":f"Bearer {settings['openrouter_api_key']}","Content-Type":"application/json"},json=payload,timeout=300)
    response.raise_for_status(); data=response.json(); usage=data.get("usage") or {}
    choices=data.get("choices") or []; message=(choices[0].get("message") or {}) if choices else {}; content=message.get("content")
    # Return even an empty answer with its paid usage. The coordinator persists
    # the ledger before output validation rejects an unusable response.
    return content or '',int(usage.get("prompt_tokens") or 0),int(usage.get("completion_tokens") or 0),float(usage.get("cost") or 0),time.monotonic()-started,str(data.get("model") or model)


def concise_english_summary(value, limit=260):
    text=re.sub(r"\s+"," ",str(value or "")).strip()
    if re.search(r"[\u3400-\u9fff]",text):
        return "The specialist returned details in an unsupported language; its decision remains available to the coordinator."
    if len(text)<=limit: return text
    shortened=text[:limit].rsplit(" ",1)[0].rstrip(" ,;:")
    return shortened+"…"


def candidate_gate_distance(axe, lighthouse, max_axe, min_lighthouse, aim=None, min_aim=None):
    """Distance from the configured automated gate; lower is better."""
    if axe is None or lighthouse is None:
        return float("inf")
    if min_aim is not None and aim is None: return float('inf')
    return max(float(axe)-float(max_axe),0.0)+max(float(min_lighthouse)-float(lighthouse),0.0)+(max(float(min_aim)-float(aim),0.0) if min_aim is not None else 0.0)


def validate_candidate_evaluation(item):
    """Reject incomplete evaluator responses before ranking or image handling."""
    if item.get('error') or item.get('status') == 'failed':
        raise RuntimeError('Candidate evaluation failed: ' + str(item.get('error') or 'The evaluator returned a failed result without details.'))
    if (item.get('axe') or {}).get('violations') is None or (item.get('lighthouse') or {}).get('accessibility_score') is None:
        raise RuntimeError('Candidate evaluation failed: Axe or Lighthouse results are missing.')
    candidate_metrics(item.get('axe') or {})


def visual_similarity(original_path, candidate_path):
    """Perceptual screenshot retention for ranking, never an accessibility gate."""
    if not original_path or not candidate_path:
        return None
    try:
        with Image.open(original_path) as left_image, Image.open(candidate_path) as right_image:
            crop_height=min(left_image.height,right_image.height,1200)
            left=left_image.convert("RGB").crop((0,0,left_image.width,crop_height)).resize((128,96))
            right=right_image.convert("RGB").crop((0,0,right_image.width,crop_height)).resize((128,96))
            mean=sum(ImageStat.Stat(ImageChops.difference(left,right)).mean)/3
            return round(max(0.0,100.0*(1.0-mean/255.0)),2)
    except (OSError,ValueError,TypeError,Image.DecompressionBombError):
        return None


def build_agent_runtime(app, run, settings, run_id, step):
    """Bind runtime skill contracts to real, validated platform tools."""
    runtime=AgentRuntime(int(step),int(run_id),float(run.get('max_cost_usd') or .25),
                         int(run.get('max_execution_seconds') or 300))
    register=runtime.tools.register
    register(ToolContract('inspect_dom','1.0','Build a bounded structural/content inventory',('html','base_url'),'object',True),
             lambda html,base_url: reconstruction_inventory(html,base_url))
    register(ToolContract('read_axe_evidence','1.0','Read bounded measured Axe failures',('path',),'array',True),
             lambda path: axe_failure_evidence(path))
    register(ToolContract('read_lighthouse_evidence','1.0','Read bounded Lighthouse accessibility failures',('path',),'array',True),
             lambda path: lighthouse_failure_evidence(path,8))
    register(ToolContract('retrieve_accessibility_evidence','1.0','Retrieve complete matching evidence pairs',('query','limit','previously_supplied'),'array',True),
             lambda query,limit,previously_supplied: rag_retrieve(query,limit,previously_supplied))
    register(ToolContract('apply_constrained_patch','1.0','Apply validated selector-scoped operations',('document','plan'),'tuple',True,True),
             lambda document,plan: apply_repair_plan(document,plan))
    register(ToolContract('prepare_frozen_widgets','2.0','Normalize recognized captured widgets for bounded replay',('html',),'tuple',True,True),
             lambda html: prepare_frozen_widget_replay(html))
    register(ToolContract('evaluate_candidate','1.0','Run Axe and Lighthouse through the evaluator service',('request_payload',),'object',True),
             lambda request_payload: _evaluate_candidate(app,request_payload))
    register(ToolContract('measure_content_retention','1.0','Measure text, URL and media retention',('original','candidate','base_url'),'object',True),
             lambda original,candidate,base_url: content_retention(original,candidate,base_url))
    register(ToolContract('compare_visual_evidence','1.0','Compare available captures for ranking only',('original_path','candidate_path'),'number_or_null',True),
             lambda original_path,candidate_path: visual_similarity(original_path,candidate_path))
    register(ToolContract('select_best_candidate','1.0','Produce deterministic candidate rank',('quality','retention','visual','step'),'tuple',True),
             lambda quality,retention,visual,step: candidate_rank(quality,retention,visual,step))
    register(ToolContract('plan_components','1.0','Detect source-owned component candidates',('html',),'array',True),
             lambda html: component_candidates(html))
    register(ToolContract('capture_screenshot','1.0','Read an existing screenshot as model visual evidence',('path',),'array',True),
             lambda path: screenshot_references(path))
    register(ToolContract('extract_content_inventory','1.0','Extract ordered content, media and controls',('html','base_url'),'object',True),
             lambda html,base_url: reconstruction_inventory(html,base_url))
    register(ToolContract('extract_markdown','1.0','Produce a source-grounded Markdown representation',('html','base_url','provider'),'object',True),
             lambda html,base_url,provider: markdown_representation(html,base_url,provider))
    register(ToolContract('apply_design_base','1.0','Enforce the selected versioned design base',('html','framework'),'tuple',True,True),
             lambda html,framework: __import__('regeneration_references').ensure_design_base(html,framework))
    return runtime


def _evaluate_candidate(app, request_payload):
    first_error=None
    for attempt in (1,2):
        try:
            response=requests.post(f"{app.config['EVALUATOR_URL']}/evaluate",json=request_payload,timeout=EVALUATOR_HTTP_TIMEOUT_SECONDS)
        except requests.Timeout as caught:
            raise RuntimeError(f'Candidate evaluation timed out after {EVALUATOR_HTTP_TIMEOUT_SECONDS} seconds; evaluator response is unavailable.') from caught
        response.raise_for_status()
        payload=response.json()
        if not payload.get('results'):
            error=RuntimeError('Candidate evaluation failed: evaluator returned no URL results.')
        else:
            item=payload['results'][0]
            try:
                validate_candidate_evaluation(item)
                if first_error:
                    item['_evaluation_retry']={'attempts':attempt,'first_error':first_error}
                return item
            except RuntimeError as caught:
                error=caught
        message=str(error)
        transient=any(signal in message for signal in ('NO_FCP','PROTOCOL_TIMEOUT','browser disconnected','Target closed','page.goto: Timeout'))
        if attempt==1 and transient:
            first_error=message
            continue
        if first_error:
            raise RuntimeError(first_error+' Retry also failed: '+message) from error
        raise error


def axe_failure_evidence(raw_path, limit=8):
    path=Path(raw_path or "")
    if not path.is_file(): return []
    try: violations=json.loads(path.read_text(encoding="utf-8"))["violations"]
    except (OSError,ValueError,KeyError,TypeError): return []
    evidence=[]
    violations = [entry for entry in violations if 'best-practice' not in entry.get('tags', [])]
    for violation in violations[:limit]:
        nodes=[]
        for node in violation.get("nodes",[])[:4]:
            nodes.append({"target":node.get("target"),"html":str(node.get("html") or "")[:500],"failure":str(node.get("failureSummary") or "")[:500],"computed_style":node.get('computed_style'),"ancestor_styles":node.get('ancestor_styles')})
        evidence.append({"rule":violation.get("id"),"impact":violation.get("impact"),"help":violation.get("help"),"nodes":nodes})
    return evidence


def backfill_accepted_remediation(app, run_id, source_base_url=None):
    """Upgrade a legacy accepted run with capture and DOM-distance evidence."""
    settings=get_settings(); conn=get_connection(); cursor=conn.cursor(dictionary=True)
    cursor.execute("""SELECT rr.*,r.url source_url,r.display_name,r.source_snapshot_path,r.response_source_path,r.axe_raw_path source_axe_raw_path,
        r.experiment_id source_experiment_id,d.storage_key,o.relative_path
        FROM remediation_runs rr JOIN experiment_results r ON r.id=rr.source_result_id
        LEFT JOIN dataset_observations o ON o.id=r.dataset_observation_id
        LEFT JOIN datasets d ON d.id=o.dataset_id WHERE rr.id=%s AND rr.status='accepted'""",(run_id,)); run=cursor.fetchone()
    if not run: cursor.close(); conn.close(); return None
    cursor.execute("SELECT * FROM remediation_iterations WHERE id=%s AND run_id=%s",(run.get("accepted_iteration_id"),run_id)); iteration=cursor.fetchone()
    source_path=_snapshot(run); candidate_path=Path(iteration["output_path"]) if iteration and iteration.get("output_path") else None
    if not iteration or not source_path or not candidate_path or not candidate_path.is_file(): cursor.close(); conn.close(); return None
    candidate_key=iteration.get("candidate_key") or str(uuid.uuid4())
    internal_url=f"http://dataset-server:8080/remediations/{run_id}/{candidate_path.name}"
    response=requests.post(f"{app.config['EVALUATOR_URL']}/evaluate",json={"experiment_id":f"remediation_publish_{run_id}","urls":[internal_url],"include_semantic":False,"include_wave":False,"axe_standard":"wcag22aa","runtime_config":evaluator_runtime_config(settings)},timeout=EVALUATOR_HTTP_TIMEOUT_SECONDS); response.raise_for_status(); item=response.json()["results"][0]
    original=source_path.read_text(encoding="utf-8",errors="replace"); candidate=candidate_path.read_text(encoding="utf-8",errors="replace"); candidate=absolutize_resources(candidate,source_base_url or document_base_url(original,run.get("source_url"))); candidate_path.write_text(candidate,encoding="utf-8"); distance,left_nodes,right_nodes=dom_distance(original,candidate)
    try: strategy=json.loads(iteration.get("strategy_json") or "{}")
    except (ValueError,TypeError): strategy={}
    strategy["taxonomy"]={"method":"Fathallah et al. (AccessGuru)",
        "original":axe_taxonomy(run.get("source_axe_raw_path")),
        "candidate":axe_taxonomy(item.get("axe",{}).get("raw_path")),
        "semantic_assessment":"specialist" if iteration.get("specialist_reviews_json") not in (None,"","[]") else "not_assessed"}
    cursor.execute("""UPDATE remediation_iterations SET candidate_key=%s,output_url=%s,screenshot_path=%s,
        dom_distance=%s,original_dom_nodes=%s,candidate_dom_nodes=%s,strategy_json=%s WHERE id=%s""",
        (candidate_key,internal_url,item.get("screenshot_path"),distance,left_nodes,right_nodes,json.dumps(strategy),iteration["id"]))
    conn.commit(); cursor.close(); conn.close(); return True


def process_remediation(app, run_id):
    settings=get_settings(); conn=get_connection(); cursor=conn.cursor(dictionary=True)
    cursor.execute("""SELECT rr.*,r.url source_url,r.captured_url,r.display_name,r.source_snapshot_path,r.response_source_path,r.screenshot_path source_screenshot_path,r.axe_raw_path source_axe_raw_path,r.lighthouse_raw_path source_lighthouse_raw_path,r.axe_wcag_violations source_axe,r.lighthouse_score source_lighthouse,r.wave_aim_score source_aim,r.experiment_id source_experiment_id,e.source_type,d.storage_key,o.relative_path,t.html_template,t.name template_name FROM remediation_runs rr JOIN experiment_results r ON r.id=rr.source_result_id JOIN experiments e ON e.id=r.experiment_id LEFT JOIN dataset_observations o ON o.id=r.dataset_observation_id LEFT JOIN datasets d ON d.id=o.dataset_id LEFT JOIN remediation_templates t ON t.id=rr.template_id WHERE rr.id=%s""",(run_id,)); run=cursor.fetchone()
    snapshot=_snapshot(run); started=time.monotonic()
    approach=approach_for(run.get("accessibility_priority"))
    agent_runtime=build_agent_runtime(app,run,settings,run_id,approach.step)
    if not snapshot: cursor.execute("UPDATE remediation_runs SET status='failed',current_phase='failed',progress_message=%s,error_message=%s,completed_at=%s WHERE id=%s",("Stored source snapshot is unavailable.","Stored source snapshot is unavailable.",_now(settings),run_id)); conn.commit(); cursor.close(); conn.close(); return
    agent_runtime.move('acquire',reason='Load immutable acquired evidence')
    _progress(cursor,conn,run_id,"acquire",5,"Loading the preserved acquired snapshot")
    best_measured_iteration=None
    try:
        cursor.execute('UPDATE remediation_runs SET axe_counting_policy=%s WHERE id=%s', (AXE_COUNTING_POLICY, run_id))
        run['axe_counting_policy'] = AXE_COUNTING_POLICY
        if run['generator_model'].startswith('openrouter/'):
            raise ValueError('Automatic model routing has been removed. Create a new run with an explicit model.')
        frozen_choice = json.loads(run.get('model_config_json') or 'null')
        if not frozen_choice:
            # Preserve existing explicit runs; never re-read an edited user catalogue.
            ident = run['generator_model'] + ('@high' if run['generator_model'] == 'openai/gpt-6-luna' and run.get('model_cost_tier') == 'xhigh' else '')
            frozen_choice = model_choice(ident)
        settings = dict(settings, _model_configuration=frozen_choice)
        run.update(use_wave=False, min_aim=None)
        if run['generator_model'].startswith('ollama/'):
            config = json.loads(run.get('local_llm_config_json') or 'null')
            if not config:
                raise ValueError('This local run has no frozen Ollama configuration.')
            settings = dict(settings, _local_llm_config=config)
        source=snapshot.read_text(encoding="utf-8",errors="replace")
        rendered_source=source
        rendered_path=Path(run.get("source_snapshot_path") or "")
        if rendered_path.is_file() and rendered_path != snapshot:
            rendered_source=rendered_path.read_text(encoding="utf-8",errors="replace")
        if run.get('execution_mode') not in REGENERATION_MODES and run.get('execution_mode') != 'single_shot':
            measured_selectors=[node['target'][0] for failure in axe_failure_evidence(run.get('source_axe_raw_path'),12)
                                for node in failure.get('nodes',[]) if isinstance(node.get('target'),list)
                                and len(node['target'])==1 and isinstance(node['target'][0],str)]
            source,source_selection=select_captured_patch_source(source,rendered_source,measured_selectors)
            if source_selection:
                _event(cursor,conn,run_id,'Frozen acquisition tool','patch_source_selection',
                       'Selected preserved rendered DOM to match the acquired content and measured patch targets',
                       dict(source_selection,source_path=str(rendered_path),stored_artifacts_modified=False))
        source,source_hydration=hydrate_static_placeholders(source,rendered_source)
        if source_hydration:
            _event(cursor,conn,run_id,'Frozen acquisition tool','source_hydration',f'Recovered {sum(item["images"] for item in source_hydration)} captured images in {len(source_hydration)} static placeholders without replaying initialized widget DOM',{'regions':source_hydration})
        single_shot=run.get('execution_mode')=='single_shot'
        whole_regeneration=run.get('execution_mode') in REGENERATION_MODES
        run['review_policy']='automated'
        if run.get('execution_mode')=='regenerate_only': run.update(max_iterations=1,use_rag=False)
        if single_shot:
            run.update(max_iterations=1,review_policy='automated',use_rag=False)
        reconstruct=approach.step in {4,5} and not single_shot and not whole_regeneration
        owned_framework=framework_assets(DATASET_ROOT) if reconstruct else None
        response_path=Path(run.get('response_source_path') or '')
        response_source=response_path.read_text(encoding='utf-8',errors='replace') if response_path.is_file() else source
        source_quality=extraction_quality(response_source,rendered_source)
        source_quality['network_response_available']=response_path.is_file()
        _event(cursor,conn,run_id,"Acquisition quality specialist","extraction_quality","Validated frozen network/rendered source views",source_quality)
        agent_runtime.move('transform',reason='Prepare lossless model and tool inputs')
        _progress(cursor,conn,run_id,"transform",12,"Separating content, media, controls, and component structure for accessible reconstruction" if reconstruct else "Preparing a lossless, selector-addressable repair context")
        evidence_mode=run.get("generator_evidence_mode") or "guided"
        feedback=""; tier=run.get("model_cost_tier") or "low"; allowed=json.loads(run.get("allowed_models_json") or "[]"); source_axe_evidence=axe_failure_evidence(run.get("source_axe_raw_path"),12); source_lighthouse_evidence=lighthouse_failure_evidence(run.get("source_lighthouse_raw_path"),8); source_taxonomy=axe_taxonomy(run.get("source_axe_raw_path")); current_axe_evidence=source_axe_evidence
        source_lighthouse_evidence,unmatched_lighthouse=grounded_lighthouse_context(source_lighthouse_evidence,source)
        current_lighthouse_evidence=source_lighthouse_evidence
        if unmatched_lighthouse:
            _event(cursor,conn,run_id,'Evidence grounding tool','unmatched_lighthouse_nodes',
                   'Excluded absent nodes from the patch prompt; original Lighthouse report and score remain unchanged',
                   {'version':'lighthouse-patch-context-v1','omitted':unmatched_lighthouse})
        ensure_remediation_resource_policy(); output_dir=DATASET_ROOT/"remediations"/str(run_id); output_dir.mkdir(parents=True,exist_ok=True)
        recorded_call = RecordedModelCalls(output_dir, agent_runtime, call_model)
        total_in=total_out=0; total_cost=0.0; accepted=None; previous_candidate=""; automated_achieved=False; pinned_effort=None
        executed_iterations=0
        pinned_effort = frozen_choice.get('reasoning_effort')
        stop_reason='Single call completed' if single_shot else 'Iteration limit reached'
        best_candidate=source; best_quality=candidate_gate_distance(run.get("source_axe"),run.get("source_lighthouse"),run["max_axe"],run["min_lighthouse"],run.get("source_aim"),run.get("min_aim")); best_visual=100.0; best_retention={}; stagnant_attempts=0; marginal_attempts=0; last_improvement_basis='initial_source'; best_axe_evidence=source_axe_evidence; best_lighthouse_evidence=source_lighthouse_evidence; best_feedback="First repair; use only the measured evidence above."
        best_rank=candidate_rank(best_quality,{},100.0,approach.step)
        best_measured_rank=None; best_measured_iteration=None
        best_screenshot_path=None
        area_state={}; area_plan=[]; component_plan=[]; planner_usage=[]; markdown_view=None
        previous_rag_ids=set()
        for number in range(1,run["max_iterations"]+1):
            iteration_tool_start=len(agent_runtime.tools.records)
            if agent_runtime.state in {'generate','evaluate'}:
                agent_runtime.move('decide',number,'Output contract or evaluation path ended without a candidate')
            agent_runtime.move('prompt',number,'Assemble current-best evidence and bounded instructions')
            initial_regeneration=whole_regeneration and number==1
            execution_approach=APPROACHES[1] if whole_regeneration else approach
            if number>1 and (total_cost>=float(run.get("max_cost_usd") or .25) or time.monotonic()-started>=int(run.get("max_execution_seconds") or 300)):
                stop_reason='Cost or time budget reached'
                _event(cursor,conn,run_id,"Budget controller","budget_stop",f"Stopped before iteration {number}: the configured cost or time budget was reached",{"cost_usd":total_cost,"seconds":time.monotonic()-started}); break
            segment=76/max(1,run["max_iterations"]); base=16+(number-1)*segment
            if evidence_mode=="independent":
                current_axe_evidence=[]; current_lighthouse_evidence=[]
                feedback="Inspect the page independently for keyboard, screen-reader, naming, contrast, and reading-order barriers. Automated evaluation remains separate; preserve all content and tasks."
            _progress(cursor,conn,run_id,"prompt",round(base),f"Retrieving relevant framework-component knowledge for iteration {number}" if reconstruct else f"Preparing measured repair instructions for iteration {number}",number)
            rag_items=[]
            rag_limit=adaptive_example_limit(current_axe_evidence,run.get('rag_top_k') or 4)
            rag_active,rag_reason=rag_activation(run.get("use_rag"),number,current_axe_evidence,current_lighthouse_evidence)
            if rag_active:
                # Measured failures are a stronger retrieval signal than the
                # page's full prose, which otherwise overwhelms ACT rule terms.
                rag_query=rag_retrieval_query(current_axe_evidence,feedback)
                rag_items=agent_runtime.tools.invoke('retrieve_accessibility_evidence',query=rag_query,limit=rag_limit,
                    previously_supplied=previous_rag_ids if stagnant_attempts else ())
                previous_rag_ids={item.get('rule_id') for item in rag_items}
                _event(cursor,conn,run_id,"Accessibility knowledge retriever","rag_retrieval",f"Retrieved {len(rag_items)} matched accessibility code examples for iteration {number}",{"iteration":number,"rules":[{"rule_id":item.get("rule_id"),"rule_name":item.get("rule_name"),"expected":item.get("expected"),"score":item.get("score"),"source":item.get("rule_page"),"provenance":item.get("source")} for item in rag_items]})
            elif run.get("use_rag"):
                message=("ACT grounding is armed and will activate only if the first measured candidate exposes a concrete failure"
                         if rag_reason=='awaiting_first_measurement' else
                         "ACT retrieval skipped because the retained candidate has no measured Axe or Lighthouse failure")
                _event(cursor,conn,run_id,"ACT knowledge retriever","rag_deferred",message,{"iteration":number,"reason":rag_reason})
            grounding=rag_prompt_context(rag_items)
            rag_quality=retrieval_evidence(rag_items,current_axe_evidence)
            rag_quality['example_limit']=rag_limit
            rag_quality['limit_policy']='Complete pairs for measured concepts; adaptive maximum 12'
            prompt_skills=agent_runtime.skills_for('prompt',rag=bool(rag_items),enabled=not single_shot)
            base_document=previous_candidate or source
            focused_context=repair_context(base_document,current_axe_evidence,current_lighthouse_evidence)
            source_base=document_base_url(source,run.get("captured_url") or run.get("source_url"))
            inventory=agent_runtime.tools.invoke('extract_content_inventory',html=source,base_url=source_base)
            inventory["base_url"]=source_base
            rendered_inventory=reconstruction_inventory(rendered_source,source_base)
            # Captured AJAX text/images are authoritative evidence too, not
            # merely visual signals. Deduplicate identical responsive/slider
            # clones while preserving the acquired reading order.
            for field,keys in [('reading_order',('element','text')),('links',('url','text')),('images',('url',))]:
                seen_records=set(); captured_records=[]
                for record in rendered_inventory[field]:
                    identity=tuple(record.get(key) for key in keys)
                    if identity in seen_records: continue
                    seen_records.add(identity); captured_records.append(record)
                inventory['captured_'+field]=captured_records
            frozen_urls={item.get("url") for item in inventory["images"]} | set(inventory.get("media_assets") or [])
            rendered_urls=observed_document_media(rendered_source,source_base)
            inventory["dynamic_images"]=[{"url":url,"source":"rendered DOM"} for url in sorted(rendered_urls-frozen_urls)][:500]
            inventory["rendered_component_signals"]=rendered_inventory["signals"][:2500]
            inventory["signals"].extend(inventory["rendered_component_signals"])
            inventory_context=serialize_reconstruction_inventory(inventory,fragmented=True) if reconstruct else ""
            prompt_axe_evidence=generator_failure_evidence(current_axe_evidence,evidence_mode)
            if evidence_mode=="localized":
                feedback="Inspect the localized elements independently. Automated checks found barriers at these targets; no automated fix recommendations are supplied. Preserve page meaning and tasks."
            framework="bootstrap"
            # Framework reconstruction knowledge is independent of ACT grounding
            # and must not encourage repair steps 1-3 to redesign the source.
            component_knowledge=retrieve_framework_knowledge(inventory,framework) if reconstruct and not single_shot else []
            if approach.step>=3 and not component_plan and not single_shot and not whole_regeneration:
                candidates=component_candidates(source if not reconstruct else rendered_source)
                planner_model=run['generator_model']
                planner_visual=screenshot_references(run.get("source_screenshot_path"))
                if not frozen_choice.get('vision'): planner_visual=[]
                if planner_model.startswith('ollama/') and not settings['_local_llm_config'].get('vision'):
                    planner_visual=[]
                planner_prompt=planning_prompt(candidates,current_axe_evidence,approach.instruction,bool(planner_visual))
                if reconstruct:
                    planner_prompt+='\nGlobal page contract: header components must be a prefix, main components the middle, footer components a suffix of the original order. Early skip links belong to header. Do not reorder content to satisfy landmarks; uncertain or interleaved regions may remain main. Plan one coherent page, not independent mini-sites.'
                planner_messages=[{"role":"user","content":[{"type":"text","text":planner_prompt},*planner_visual] if planner_visual else planner_prompt}]
                _event(cursor,conn,run_id,"Architecture planning specialist","planning",f"Planning {len(candidates)} grounded components and dependencies",{"model":planner_model,"approach":approach.name})
                proposal,pi,po,pc,ps,pa=recorded_call(settings,planner_model,planner_prompt,True,.1,tier,allowed,planner_messages,reasoning_override=pinned_effort)
                planner_response_path=output_dir/f'attempt-{number}-planner-response.txt'
                planner_response_path.write_text(proposal,encoding='utf-8')
                _event(cursor,conn,run_id,'Architecture planning specialist','planning_response','Planner response saved before contract validation',{'model':pa,'response_path':str(planner_response_path),'input_tokens':pi,'output_tokens':po})
                total_in+=pi; total_out+=po; total_cost+=pc
                cursor.execute("UPDATE remediation_runs SET total_input_tokens=%s,total_output_tokens=%s,total_cost_usd=%s WHERE id=%s",(total_in,total_out,total_cost,run_id)); conn.commit()
                planner_usage=[{"role":"Architecture planning specialist","model":pa,"input_tokens":pi,"output_tokens":po,"cost_usd":pc,"seconds":ps}]
                component_plan=validate_component_plan(parse_json_response(proposal),candidates)
                if reconstruct: component_plan=coherent_regions(component_plan)
                if reconstruct and run.get("reconstruction_mode")=="fragmented": area_plan=reconstruction_tasks(component_plan)
                _event(cursor,conn,run_id,"Architecture planning specialist","plan_validated","Every component assigned once; source order and ownership verified",{"components":[{k:v for k,v in item.items() if k!="source" and k!="text"} for item in component_plan],"usage":planner_usage})
            if not single_shot and (reconstruct or approach.step==4) and run.get("transformation_format")=="markdown" and markdown_view is None:
                markdown_view=markdown_representation(rendered_source,source_base,run.get("markdown_provider") or "local")
                _event(cursor,conn,run_id,"Markdown transformation specialist","markdown",f"Prepared {markdown_view['provider']} Markdown alongside authoritative UI inventory",{k:v for k,v in markdown_view.items() if k!="markdown"})
            if reconstruct:
                born_manifest=content_manifest(component_plan,source_base,verified_components=approach.step==5)
                if approach.step==5:
                    for owned_block in born_manifest:
                        if owned_block.get('composition_units'): owned_block['require_composition']=True
                assembly_instruction=COMPOSITION_INSTRUCTION if approach.step==5 else "CONTENT-LOCKED ASSEMBLY: The assembler supplies ALL original text, images, links and native forms in protected content blocks. Do NOT rewrite their content. For EACH component below emit exactly one EMPTY div, section or article with data-warp-slot=\"component id\". Include ALL slots in the listed original order, not nested, not hidden. Place header/navigation blocks in a header, main content in exactly one main, footer blocks in a footer, following the global plan. Use a readable restrained design, generous spacing, no solid-color rectangles around every block, and no fixed heights or clipped content. Make menu content visible; do not invent new navigation labels or headings. You may use the original page title once. Source widgets become static readable content; native forms retain their original submission contracts. Do not add application-specific JavaScript. Use only framework disclosure behavior if necessary. The protected blocks preserve internal reading order and content relationships; design the surrounding layout, not replacement summaries."
                prompt=f"""You are a born-accessible web reconstruction agent. Return one complete standalone HTML document, not JSON and not an explanation. Create a coherent global design using Bootstrap, NOT a collection of independent mini-pages. Never substitute an iframe of, or redirect to, the original page.

{assembly_instruction}
Protected block manifest: {manifest_context(born_manifest)}

Reconstruct the acquired page with {framework.title()} components and semantic native HTML. This is not a generic redesign: preserve every original text, link destination, meaningful image URL, form field, control, data item, and user task. The dynamic_images inventory comes from the rendered browser DOM and is authoritative for banners, carousel slides and promotional strips that were absent from the network response: preserve those meaningful assets and their context. Use the screenshot to understand hierarchy, branding, banners, menus, carousels, cards and grouping; visual resemblance is secondary to the preservation policy. Do not invent or summarize content. Resolve resources with the exact absolute URLs in the inventory. Include Bootstrap CSS and bootstrap.bundle JS from the official CDN only when a Bootstrap component needs them. Prefer native elements over ARIA and avoid autoplay.

Iteration: {number} of {run['max_iterations']}
Preservation policy: {preservation_instruction(35 if whole_regeneration else int(run.get('accessibility_priority') or 55))}
Structured page inventory: {inventory_context}
Retrieved framework component knowledge: {json.dumps(component_knowledge,ensure_ascii=False)}
Retrieved W3C ACT evidence: {grounding}
Measured Axe failures: {json.dumps(prompt_axe_evidence,ensure_ascii=False)}
Measured Lighthouse failures: {json.dumps(current_lighthouse_evidence,ensure_ascii=False)}
Previous evaluation feedback: {feedback or 'First reconstruction: preserve the complete page meaning and task inventory.'}
Previous layout to refine (protected blocks emptied): {layout_only(base_document) if number>1 else 'None'}

The output must start with <!doctype html> and end with </html>."""
            else:
                prompt=f"""You are an accessibility program-repair agent. Produce a constrained JSON patch plan for the complete current HTML document; the system applies your operations to that document, so you must not regenerate or summarize the page.

Iteration: {number} of {run['max_iterations']}
Preservation policy: {preservation_instruction(35 if whole_regeneration else int(run.get('accessibility_priority') or 55))}
Measured Axe failures: {json.dumps(prompt_axe_evidence,ensure_ascii=False)}
Measured Lighthouse accessibility failures: {json.dumps(current_lighthouse_evidence,ensure_ascii=False)}
Focused document context: {focused_context}
Retrieved component knowledge: {json.dumps(component_knowledge,ensure_ascii=False)}
Retrieved W3C ACT evidence: {grounding}
Previous evaluation feedback: {feedback or 'First repair; use only the measured evidence above.'}

Return one JSON object with an operations array and a rationale. Allowed operations are:
- {{"action":"set_attribute","selector":"valid CSS selector","name":"attribute","value":"value"}}
- {{"action":"remove_attribute","selector":"valid CSS selector","name":"attribute"}}
- {{"action":"replace_element","selector":"specific selector","html":"complete replacement element"}}
- {{"action":"insert_before" or "insert_after","selector":"specific selector","html":"markup"}}
- {{"action":"append_css","css":"targeted override rules"}}
- {{"action":"append_head_html" or "append_body_html","html":"markup"}}

Measured findings are fallible localization evidence, not permission to game the evaluator. Check each finding against the actual element and surrounding task. Inspect the independent overview for additional barriers. Group related failures by root cause and coordinate HTML and targeted CSS repairs. Use the exact selectors from measured evidence whenever possible. Make the fewest local changes that fix the reported failures. Never replace html, head, or body; never remove content, links, forms, scripts, stylesheets, SVG contents, data, or behavior. Never conceal violations with role=presentation. Never assign role=main to body, an empty placeholder, or a container that excludes most page content. For contrast/focus failures, append narrowly scoped CSS overrides. For semantic names or alternatives, infer wording only from adjacent text, title, filename, or existing context; do not invent facts. Retrieved snippets are component knowledge, not page templates. Return JSON only."""
                prompt+='\nEvery repair selector must address an existing element in the supplied current document context. Do not invent IDs or reuse IDs from a different browser state. If no justified executable repair is available, return an empty operations array; the unchanged candidate will be measured rather than treating rejected operations as a repair.'
            prompt+="\nVersioned intervention contract: "+execution_approach.name+". "+execution_approach.instruction
            generation_skills=agent_runtime.skills_for('generate',enabled=not single_shot)
            iteration_skills=list({skill.id:skill for skill in [*prompt_skills,*generation_skills]}.values())
            if iteration_skills:
                prompt+='\nVersioned runtime skills:\n'+agent_runtime.catalog.prompt_context(iteration_skills)
                _event(cursor,conn,run_id,'Skill orchestrator','skills_activated',
                    f'Activated {len(iteration_skills)} versioned skills for iteration {number}',
                    {'iteration':number,'skills':[skill.evidence() for skill in iteration_skills],
                     'manifest_sha256':agent_runtime.catalog.manifest_sha256})
            if not reconstruct and not single_shot:
                prompt+=f'\nOUTPUT BUDGET: at most {execution_approach.max_operations} concise operations. Prioritize measured root causes. Do not copy the complete page or large unchanged HTML/CSS into the JSON. Every string must be JSON-escaped; finish the object within the output token budget.'
            if approach.step>=2:
                prompt+='\nFor orphan list items you may use {"action":"wrap_element","selector":"specific orphan li selector","tag":"ul" or "ol"}; this moves the original node, preserving content and handlers. Do not replace list items with presentation roles.'
            if approach.step==3:
                prompt+='\nAdditional behavior operation: {"action":"append_javascript","selector":"existing specific component selector","javascript":"local event handlers"}. Use only for measured keyboard/focus behavior; no network/navigation/storage/eval. Prefer native details/summary when replacing a disclosure. Do not break original form submission or handlers.'
            prompt+="\nArchitecture plan: "+json.dumps([{k:v for k,v in item.items() if k!="source" and k!="text"} for item in component_plan],ensure_ascii=False)
            if markdown_view: prompt+="\nSupplementary frozen Markdown (UI inventory remains authoritative):\n"+markdown_view["markdown"]
            if single_shot: prompt=baseline_prompt(source)
            if whole_regeneration and not initial_regeneration:
                prompt+='\nRetain the selected design base and its stylesheet. Do not substitute frameworks or restore the old source theme. Selected base: '+DESIGN_BASES[selected_framework(run.get('template_selection'))][0]+'\n'+component_instruction(selected_framework(run.get('template_selection')))
                prompt+='\nExact acquired link labels, destinations and images still missing from the best current page: '+json.dumps(resource_omissions(rendered_source,base_document,source_base),ensure_ascii=False)+'\nThis current preservation evidence remains applicable even after invalid-output feedback. Restore omissions in their appropriate current sections using short local patches; never substitute a metric-only fix for recovery of missing page tasks and information.'
                prompt+='\nExact acquired native form contracts missing from the regenerated page: '+json.dumps(task_omissions(rendered_source,base_document,source_base),ensure_ascii=False)+'\nRestore these actions and named fields locally, retaining current layout and accessible labels.'
                prompt+='\nExact acquired content potentially omitted or paraphrased in the regenerated page: '+json.dumps(omission_context(rendered_source,base_document,source_base),ensure_ascii=False)+'\nRestore substantive omissions with local text/element patches in their appropriate current section. This evidence is content only, not permission to restore the old layout. Keep the regenerated architecture, acquired tasks and all existing content.'
            regeneration_evidence={}
            if initial_regeneration:
                content=rendered_source
                provider='frozen browser DOM (not Crawl4AI)'
                if run.get('transformation_format')=='markdown':
                    markdown_view=markdown_representation(rendered_source,source_base,run.get('markdown_provider') or 'local')
                    if run.get('markdown_provider')=='jina' and markdown_view['provider']!='jina':
                        raise ValueError('Requested Jina baseline unavailable; local Markdown is not substituted for this experiment')
                    content=markdown_view['markdown']; provider=markdown_view['provider']
                original_messages=generation_messages(content,source_base,reference_document=rendered_source,framework=selected_framework(run.get('template_selection')))
                regeneration_evidence=generation_evidence(original_messages,run['transformation_format'],provider,run['temperature'])
                if run.get('transformation_format')=='markdown':
                    quality_check=markdown_quality(rendered_source,content,source_base)
                    regeneration_evidence['acquisition_quality']=quality_check
                    if quality_check['missing_images'] or quality_check['missing_links'] or quality_check['text_vocabulary_retained_percent']<95:
                        raise ValueError('Markdown acquisition is incomplete; no generation call made: '+json.dumps(quality_check))
                prompt='\n\n'.join(message['content'] for message in original_messages)
            if len(prompt)>400000: raise ValueError("Combined specialist context exceeds budget; no content was silently truncated")
            agent_runtime.move('generate',number,'Invoke bounded generator or repair agent')
            _progress(cursor,conn,run_id,"generate",round(base+segment*.22),f"{'Single-shot baseline' if single_shot else approach.name}: generating candidate {number}",number)
            iteration_temperature=(min(float(run["temperature"]),0.30 if approach.step>=4 else 0.05) if number>1 else float(run["temperature"]))
            if whole_regeneration: iteration_temperature=float(run['temperature']) if initial_regeneration else .05
            requested_generator=run["generator_model"]
            message_content=[{"type":"text","text":prompt}]
            visual_reference=screenshot_references(run.get("source_screenshot_path")) if reconstruct else ([screenshot_message(run.get("source_screenshot_path"))] if approach.step>=3 and not single_shot else [])
            visual_reference=[reference for reference in visual_reference if reference]
            if initial_regeneration: visual_reference=[]
            elif whole_regeneration:
                candidate_capture=screenshot_message(best_screenshot_path)
                source_capture=screenshot_message(run.get("source_screenshot_path"))
                visual_reference=[reference for reference in (candidate_capture,source_capture) if reference]
                if not frozen_choice.get('vision'):
                    visual_reference=[]
                if visual_reference:
                    message_content[0]['text']+='\nVisual refinement evidence: the first attached capture is the best regenerated page. The second, when present, is the immutable original capture. Use the original only to recover hierarchy, grouping, proportions and meaningful media context; retain the regenerated framework architecture and do not restore inaccessible source widgets or styling.'
            if not frozen_choice.get('vision'): visual_reference=[]
            if requested_generator.startswith('ollama/') and not settings['_local_llm_config'].get('vision'):
                visual_reference=[]
            if visual_reference: message_content.extend(visual_reference)
            diagnosis=None; diagnosis_usage=[]
            local_generator=requested_generator.startswith('ollama/')
            ambiguous_evidence=number>1 and not current_axe_evidence and bool(current_lighthouse_evidence)
            diagnosis_policy=run.get('diagnosis_policy') or 'disabled'
            if diagnosis_needed(single_shot,initial_regeneration,reconstruct,local_generator,
                                stagnant=stagnant_attempts>0,ambiguous=ambiguous_evidence,
                                policy=diagnosis_policy):
                dp=diagnosis_prompt(focused_context,current_axe_evidence,current_lighthouse_evidence,feedback,execution_approach,whole_regeneration)
                dm=[{'role':'user','content':[{'type':'text','text':dp},*visual_reference] if visual_reference else dp}]
                _progress(cursor,conn,run_id,'prompt',round(base+segment*.20),f'Diagnosing focused accessibility repairs for attempt {number}',number)
                raw,di,do,dc,ds,actual_diagnostician=recorded_call(settings,requested_generator,dp,True,.05,cost_tier=tier,allowed_models=allowed,messages=dm,reasoning_override=pinned_effort,output_token_limit=1200)
                total_in+=di; total_out+=do; total_cost+=dc
                cursor.execute('UPDATE remediation_runs SET total_input_tokens=%s,total_output_tokens=%s,total_cost_usd=%s,execution_seconds=%s WHERE id=%s',(total_in,total_out,total_cost,time.monotonic()-started,run_id));conn.commit()
                diagnostic_path=output_dir/f'attempt-{number}-diagnosis-response.txt'
                diagnostic_path.write_text(raw,encoding='utf-8')
                try: diagnosis=grounded_diagnosis(parse_json_response(raw),base_document,current_axe_evidence)
                except (ValueError,TypeError): diagnosis={'version':'grounded-pre-patch-diagnosis-v1','status':'invalid_output','findings':[],'acceptance_gate':False,'reason':'Malformed diagnosis; generator still receives measured evidence'}
                _event(cursor,conn,run_id,'Accessibility diagnosis agent','patch_diagnosis','Conditional pre-patch diagnosis completed after stagnation or ambiguous evidence; unsupported recommendations are excluded',{'iteration':number,'model':actual_diagnostician,'diagnosis':diagnosis,'response_path':str(diagnostic_path),'input_tokens':di,'output_tokens':do,'cost_usd':dc,'trigger':'stagnation' if stagnant_attempts else 'ambiguous_evidence'})
                diagnosis_usage=[{'role':'Accessibility diagnosis agent','model':actual_diagnostician,'input_tokens':di,'output_tokens':do,'cost_usd':dc,'seconds':ds}]
                prompt+='\nGrounded pre-patch diagnosis (advice only; intervention guards still apply): '+json.dumps(diagnosis,ensure_ascii=False)
                message_content[0]['text']=prompt
                if total_cost>=float(run.get('max_cost_usd') or .25) or time.monotonic()-started>=int(run.get('max_execution_seconds') or 300):
                    stop_reason='Cost or time budget reached after diagnosis; best evaluated result retained'
                    break
            elif local_generator and not (single_shot or initial_regeneration or reconstruct):
                diagnosis={'version':'deterministic-measured-evidence-v1','status':'not_called',
                    'findings':[],'acceptance_gate':False,
                    'reason':'Local lean path: measured Axe/Lighthouse evidence is supplied directly to the generator.'}
                _event(cursor,conn,run_id,'Deterministic diagnosis tool','patch_diagnosis_skipped',
                    'Skipped the duplicate local-model diagnosis call; generator receives measured evidence directly',
                    {'iteration':number,'model':requested_generator,'diagnosis':diagnosis})
            # Current best HTML, findings and feedback already carry the loop
            # state. Replaying all full prompts duplicates source and stale errors.
            request_messages=[{"role":"user","content":message_content if visual_reference else prompt}]
            if initial_regeneration: request_messages=original_messages
            generation_usage=[]
            if area_plan:
                area_state['born_manifest']=born_manifest
                area_state["feedback"]=feedback
                area_state['act_grounding']=grounding
                area_state["remaining_budget"]=float(run.get("max_cost_usd") or .25)-total_cost
                area_state["deadline"]=started+int(run.get("max_execution_seconds") or 300)
                partial_usage={"input_tokens":0,"output_tokens":0,"cost_usd":0.0}
                def area_event(actor,kind,message,details):
                    _event(cursor,conn,run_id,actor,kind,message,details)
                    if kind in {"area_generate","area_assemble","area_retained"}:
                        cursor.execute("UPDATE remediation_runs SET progress_message=%s,progress_updated_at=%s WHERE id=%s",(_bounded_progress(message),_now(settings),run_id)); conn.commit()
                    if kind=="area_generated":
                        for key in partial_usage: partial_usage[key]+=details.get(key,0)
                        cursor.execute("UPDATE remediation_runs SET total_input_tokens=%s,total_output_tokens=%s,total_cost_usd=%s,execution_seconds=%s WHERE id=%s",(total_in+partial_usage["input_tokens"],total_out+partial_usage["output_tokens"],total_cost+partial_usage["cost_usd"],time.monotonic()-started,run_id)); conn.commit()
                def area_model_call(*args,**kwargs):
                    result=recorded_call(*args,**kwargs,reasoning_override=area_state.get('requested_effort',pinned_effort))
                    return result
                try:
                    generated,generation_usage,actual_generator=regenerate_areas(area_plan,inventory,settings,requested_generator,iteration_temperature,tier,allowed,area_model_call,reconstruction_inventory,retrieve_framework_knowledge,parse_json_response,visual_reference,area_state,area_event)
                except ReconstructionBudgetStop as budget_stop:
                    # Paid area calls were already persisted by area_event.
                    # Reconcile in-memory totals before the normal terminal
                    # decision, keeping the last fully evaluated candidate.
                    total_in+=partial_usage['input_tokens']
                    total_out+=partial_usage['output_tokens']
                    total_cost+=partial_usage['cost_usd']
                    stop_reason='Cost or time budget reached during fragment reconstruction'
                    _event(cursor,conn,run_id,'Budget controller','budget_stop',str(budget_stop),{'partial_area_usage':partial_usage,'complete_candidate_preserved':bool(executed_iterations)})
                    break
                prompt="\n\n".join(item.pop("prompt") for item in generation_usage)
                ti=sum(item["input_tokens"] for item in generation_usage); to=sum(item["output_tokens"] for item in generation_usage); cost=sum(item["cost_usd"] for item in generation_usage); gen_seconds=sum(item["seconds"] for item in generation_usage)
            else:
                generated,ti,to,cost,gen_seconds,actual_generator=recorded_call(settings,requested_generator,prompt,json_mode=not reconstruct and not single_shot and not initial_regeneration,temperature=iteration_temperature,cost_tier=tier,allowed_models=allowed,messages=request_messages,reasoning_override=pinned_effort,output_token_limit=(32000 if initial_regeneration else 4000) if whole_regeneration else None)
            # Record paid calls before parsing/evaluation can fail. Successful
            # iterations reconcile this ledger with reviewer/planner usage below.
            cursor.execute("UPDATE remediation_runs SET total_input_tokens=%s,total_output_tokens=%s,total_cost_usd=%s,execution_seconds=%s WHERE id=%s",(total_in+ti,total_out+to,total_cost+cost,time.monotonic()-started,run_id)); conn.commit()
            if actual_generator != requested_generator:
                raise ValueError('Provider returned a different model than the explicit selection; paid usage recorded.')
            baseline_evidence={}
            if initial_regeneration:
                raw_output=output_dir/'one-shot-original-response.html'
                raw_output.write_text(generated,encoding='utf-8')
                candidate=complete_candidate(generated,source,source_base)
                patch_result={'applied':[{'action':'whole_document_regeneration'}],'skipped':[]}
            elif single_shot:
                candidate,baseline_evidence=baseline_candidate(generated,source,source_base)
                baseline_evidence['assessment']=generated
                baseline_evidence['input_scope']='complete frozen page; original paper used snippets'
                baseline_evidence['prompt_version']='full-page correction adaptation v2; original question plus complete-output instruction'
                patch_result={'applied':[{'action':'single_shot_response','output':baseline_evidence['output']}],'skipped':[]}
            elif reconstruct:
                raw_output=output_dir/f'attempt-{number}-born-layout.html'
                raw_output.write_text(generated,encoding='utf-8')
                candidate=complete_html_response(generated)
                if "<html" not in candidate.lower() or "</html>" not in candidate.lower(): raise ValueError("The reconstruction model did not return a complete HTML document.")
                if not area_plan:
                    try:
                        candidate=bind_content(candidate,born_manifest,document_title=inventory.get('title'))
                    except ValueError as error:
                        total_in+=ti; total_out+=to; total_cost+=cost
                        feedback=f'Your layout violated the protected content contract: {error}. Preserve every component exactly once in source order. '+('Compose each slot using every EMPTY owned data-warp-unit reference exactly once; wrappers supply Bootstrap layout only.' if approach.step==5 else 'Return every EMPTY data-warp-slot content container.')+' No rewritten or summarized content.'
                        _event(cursor,conn,run_id,'Content contract guard','invalid_output',feedback,{'attempt':number,'model':actual_generator,'cost_usd':cost,'input_tokens':ti,'output_tokens':to,'response_path':str(raw_output)})
                        if number==run['max_iterations']: stop_reason='Content layout contract was not achieved within the attempt limit'
                        continue
                if original_page_wrapper(candidate,source,source_base):
                    raise ValueError('Embedding the unchanged original page is not a born-accessible reconstruction.')
                patch_result={"applied":[{"action":"component_reconstruction","components":[item["component"] for item in component_knowledge]}],"skipped":[]}
            else:
                raw_output=output_dir/f'attempt-{number}-response.txt'
                raw_output.write_text(generated,encoding='utf-8')
                try:
                    plan=parse_json_response(generated)
                    if not isinstance(plan.get('operations'),list) or any(not isinstance(operation,dict) for operation in plan['operations']):
                        raise ValueError('Repair output requires an operations array of objects')
                except ValueError as error:
                    total_in+=ti; total_out+=to; total_cost+=cost
                    feedback=f'Your preceding response was not executable JSON: {str(error)[:240]}. The previous best page is unchanged. Return a SHORT valid JSON object with operations; fewer narrowly scoped repairs, no copied full document. Do not repeat the malformed response.'
                    _event(cursor,conn,run_id,'Output contract guard','invalid_output',feedback,{'attempt':number,'model':actual_generator,'response_path':str(raw_output),'input_tokens':ti,'output_tokens':to,'cost_usd':cost})
                    if number==run['max_iterations']: stop_reason='Output contract was not achieved within the attempt limit'
                    continue
                plan,scope_rejections=constrain_plan(base_document,plan,APPROACHES[1] if whole_regeneration else approach,[item["selector"] for item in component_plan if item["intervention"]=="regenerate"],source_base)
                candidate,patch_result=agent_runtime.tools.invoke('apply_constrained_patch',document=base_document,plan=plan)
                patch_result["skipped"].extend(scope_rejections)
                recorded_call.checkpoint()
            design_base_evidence=None
            if whole_regeneration:
                from regeneration_references import ensure_design_base
                candidate,design_base_evidence=ensure_design_base(candidate,selected_framework(run.get('template_selection')))
            candidate,deterministic_repairs=apply_deterministic_repairs(candidate,current_axe_evidence,current_lighthouse_evidence) if evidence_mode in {"guided","localized"} and not single_shot and not initial_regeneration else (candidate,[])
            frozen_widget_repairs=[]
            if not reconstruct and not single_shot and not whole_regeneration:
                candidate,frozen_widget_repairs=agent_runtime.tools.invoke('prepare_frozen_widgets',html=candidate)
                if frozen_widget_repairs:
                    _event(cursor,conn,run_id,'Frozen acquisition tool','widget_replay_normalization','Prepared recognized captured widgets for bounded replay with their frozen data',{'repairs':frozen_widget_repairs,'limitations':'Library-specific adapters; unknown widgets and application tasks require testing'})
            resource_repairs=[]
            if reconstruct:
                candidate=embed_framework(candidate,owned_framework)
                candidate,resource_repairs=preserve_resources(candidate,rendered_source,source_base)
                if resource_repairs:
                    _event(cursor,conn,run_id,'Content assembly tool','resources_retained',f'Restored {len(resource_repairs)} omitted original resources in an explicit fallback section',{'repairs':resource_repairs,'limitations':'Resource presence does not certify task functionality or semantic equivalence'})
            no_op=measurable_noop(patch_result) and not deterministic_repairs
            if no_op:
                _event(cursor,conn,run_id,'Patch executor','no_op',
                       'No edits requested; evaluate the unchanged candidate instead of treating an empty plan as a fatal error',
                       {'iteration':number,'acceptance':'Determined only by new measurements'})
            if not patch_result["applied"] and not deterministic_repairs and not no_op:
                total_in+=ti; total_out+=to; total_cost+=cost
                execution_errors=[{'action':entry.get('operation',{}).get('action'),
                                   'selector':entry.get('operation',{}).get('selector'),
                                   'reason':entry.get('reason')} for entry in patch_result['skipped'][:12]]
                feedback='Your preceding plan had no applicable operations. The previous best page is unchanged. Correct these execution errors with a short, scoped operations array: '+json.dumps(execution_errors,ensure_ascii=False)
                _event(cursor,conn,run_id,'Output contract guard','invalid_output',feedback,{'attempt':number,'model':actual_generator,'response_path':str(raw_output),'input_tokens':ti,'output_tokens':to,'cost_usd':cost})
                if number==run['max_iterations']: stop_reason='No applicable repair operations were produced within the attempt limit'
                continue
            _event(cursor,conn,run_id,"Component reconstruction" if reconstruct else "Patch executor","reconstruction" if reconstruct else "patch",f"Reconstructed candidate {number} with {framework.title()} knowledge for {', '.join(item['component'] for item in component_knowledge)}" if reconstruct else f"Applied {len(patch_result['applied'])} constrained repairs and skipped {len(patch_result['skipped'])} invalid or unmatched operations for candidate {number}",{"iteration":number,"result":patch_result,"framework":framework,"visual_reference":bool(visual_reference)})
            candidate=standalone_reconstruction(candidate,source_base) if reconstruct else absolutize_resources(candidate,source_base); candidate_key=str(uuid.uuid4()); path=output_dir/f"candidate-{candidate_key}.html"; path.write_text(candidate,encoding="utf-8"); distance,original_nodes,candidate_nodes=dom_distance(source,candidate); retention=agent_runtime.tools.invoke('measure_content_retention',original=source,candidate=candidate,base_url=source_base)
            dynamic_required={item.get("url") for item in inventory.get("dynamic_images") or [] if item.get("url")}
            candidate_inventory=reconstruction_inventory(candidate,source_base); candidate_image_urls={item.get("url") for item in candidate_inventory["images"] if item.get("url")}
            retention["dynamic_images_percent"]=round(100*len(dynamic_required & candidate_image_urls)/max(1,len(dynamic_required)),2) if dynamic_required else 100.0
            retention["dynamic_images_required"]=len(dynamic_required); retention["dynamic_images_retained"]=len(dynamic_required & candidate_image_urls)
            url=f"http://dataset-server:8080/remediations/{run_id}/{path.name}"
            tools="Axe and Lighthouse"+(" and WAVE AIM" if run["use_wave"] else "")
            agent_runtime.move('evaluate',number,'Execute deterministic candidate measurements')
            # A scientific single-shot baseline is still measured with the
            # same deterministic tools, but must not activate an agent skill.
            evaluation_skills=agent_runtime.skills_for('evaluate',enabled=not single_shot)
            iteration_skills=list({skill.id:skill for skill in [*iteration_skills,*evaluation_skills]}.values())
            _progress(cursor,conn,run_id,"evaluate",round(base+segment*.58),f"Evaluating candidate {number} with {tools}",number)
            item=agent_runtime.tools.invoke('evaluate_candidate',request_payload={"experiment_id":f"remediation_{run_id}_{number}","urls":[url],"include_semantic":False,"include_wave":bool(run["use_wave"]),"axe_standard":"wcag22aa","runtime_config":evaluator_runtime_config(settings)})
            if item.get('_evaluation_retry'):
                _event(cursor,conn,run_id,'Evaluation team','evaluation_retry',
                    'Transient evaluator failure recovered on a bounded retry',item['_evaluation_retry'])
            try:
                validate_candidate_evaluation(item)
            except RuntimeError as evaluation_error:
                _event(cursor,conn,run_id,'Evaluator','evaluation_failed',str(evaluation_error),
                    {'iteration':number,'response':item})
                raise
            evaluated_snapshot=Path(item.get("source_snapshot_path") or "")
            capture_replay_warnings=[]
            if evaluated_snapshot.is_file():
                retention.update(rendered_media_retention(rendered_source,evaluated_snapshot.read_text(encoding="utf-8",errors="replace"),source_base))
                if not reconstruct:
                    capture_replay_warnings=captured_widget_replay_warnings(rendered_source,evaluated_snapshot.read_text(encoding='utf-8',errors='replace'))
                    if capture_replay_warnings:
                        _event(cursor,conn,run_id,'Capture replay audit','widget_replay_warning','Captured widgets created additional native controls when original scripts replayed; inspect interactive behavior',{'warnings':capture_replay_warnings,'acceptance_gate':False})
            measured_axe = candidate_metrics(item.get('axe', {}))
            wave=item.get("wave",{}); axe=measured_axe['axe_wcag_violations']; lighthouse=item.get("lighthouse",{}).get("accessibility_score"); aim=wave.get("aim_score"); wave_credits=int(wave.get("credits_used") or 0); wave_cost=float(wave.get("cost_usd") or 0)
            axe_evidence=axe_failure_evidence(item.get("axe",{}).get("raw_path"))
            lighthouse_evidence=lighthouse_failure_evidence(item.get("lighthouse",{}).get("raw_path"),8)
            current_axe_evidence=axe_evidence; current_lighthouse_evidence=lighthouse_evidence
            area_checkpoints={}
            if area_plan:
                area_checkpoints=checkpoint_areas(area_state,candidate,item.get("axe",{}).get("raw_path"),area_plan,source_base)
                if lighthouse is None or lighthouse<run["min_lighthouse"]:
                    for task in area_plan: area_state.get(task.get("key",task["area"]),{})["reuse"]=False
                    area_checkpoints["retained"]=[]
                    area_checkpoints["reuse_disabled_reason"]="Unlocalized Lighthouse failures require full-context refinement"
                _event(cursor,conn,run_id,"Regression guard","area_checkpoints","Area checkpoints prepared for the next assembly; retained: "+", ".join(area_checkpoints.get("retained",[]))+"; restored: "+", ".join(area_checkpoints.get("restored",[])),area_checkpoints)
            _event(cursor,conn,run_id,"Axe, Lighthouse"+(" and WAVE" if run["use_wave"] else ""),"metrics",f"Candidate {number}: Axe {axe if axe is not None else '—'}, Lighthouse {lighthouse if lighthouse is not None else '—'}, content {retention['text_percent']}%, links {retention['links_percent']}%, DOM divergence {distance}%"+(f", WAVE AIM {aim}" if aim is not None else ""),{"iteration":number,"axe":axe,"lighthouse":lighthouse,"wave_aim":aim,"dom_divergence":distance,"content_retention":retention,"axe_failures":axe_evidence})
            dom_pass=not bool(run.get("enforce_dom_distance")) or distance<=float(run.get("max_dom_distance") or 70)
            content_pass=retention["text_percent"]>=90 and retention["links_percent"]>=85 and retention["images_percent"]>=85 and retention["dynamic_images_percent"]>=85
            # Only the visible automated thresholds decide this gate. Content
            # retention and DOM preservation remain reproducible warnings.
            metric_pass=(axe is not None and axe<=run["max_axe"] and lighthouse is not None and lighthouse>=run["min_lighthouse"] and (run["min_aim"] is None or (aim is not None and float(aim)>=float(run["min_aim"]))))
            acceptance_pass=metric_pass
            automated_achieved=automated_achieved or acceptance_pass
            _progress(cursor,conn,run_id,"evaluate",round(base+segment*.78),f"Reviewing candidate {number} against automated targets",number)
            exact_feedback=(achieved_feedback(axe_evidence,lighthouse_evidence) if acceptance_pass else "Refine the preceding candidate using the exact evidence below. Restore every missing content item, destination, and acquired media URL exactly; do not summarize the source.\nAxe failures:\n"+json.dumps(axe_evidence,ensure_ascii=False)+"\nLighthouse accessibility failures:\n"+json.dumps(lighthouse_evidence,ensure_ascii=False)+"\nAutomated preservation evidence:\n"+json.dumps(retention,ensure_ascii=False))
            gate_reason=f"Axe {axe} (required ≤ {run['max_axe']}); Lighthouse {lighthouse} (required ≥ {run['min_lighthouse']})"
            if run.get('min_aim') is not None:
                gate_reason+=f"; WAVE AIM {aim} (required ≥ {run['min_aim']})"
            gate_reason+=': thresholds achieved.' if acceptance_pass else ': thresholds not achieved.'
            decision_data={"decision":"accept" if acceptance_pass else "refine","reason":gate_reason+" Preservation is reported separately.","feedback":exact_feedback}; actual_reviewer="system/automated-gate"
            decision="accept" if acceptance_pass and decision_data.get("decision")=="accept" else "refine"; raw_feedback=decision_data.get("feedback") or decision_data.get("reason") or "Refine the remaining accessibility barriers."; feedback=("\n".join(str(item) for item in raw_feedback) if isinstance(raw_feedback,list) else str(raw_feedback))[:8000]
            if patch_result['skipped']:
                rejected=[{'action':entry.get('operation',{}).get('action'),
                           'selector':entry.get('operation',{}).get('selector'),
                           'reason':entry.get('reason')} for entry in patch_result['skipped']]
                feedback='Execution feedback: these operations were not applied. Do not repeat them; use the substantive existing containers and valid selectors from the context.\n'+json.dumps(rejected,ensure_ascii=False)+'\n'+feedback
            quality=candidate_gate_distance(axe,lighthouse,run["max_axe"],run["min_lighthouse"],aim,run.get("min_aim"))
            visual=agent_runtime.tools.invoke('compare_visual_evidence',original_path=run.get("source_screenshot_path"),candidate_path=item.get("screenshot_path"))
            rank=agent_runtime.tools.invoke('select_best_candidate',quality=quality,retention=retention,visual=visual,step=approach.step)
            missing_tasks=task_omissions(rendered_source,candidate,source_base) if whole_regeneration else []
            if whole_regeneration: rank=(rank[0],len(missing_tasks),*rank[1:])
            is_best=rank<best_rank
            # The regenerated document, not the acquired original, owns the
            # refinement baseline even when its measured targets are worse.
            if initial_regeneration: is_best=True
            if is_best:
                if initial_regeneration:
                    marginal_attempts=0; last_improvement_basis='regenerated_baseline'
                else:
                    useful,last_improvement_basis=meaningful_improvement(best_quality,quality,best_retention,retention,best_visual,visual,approach.step)
                    marginal_attempts=0 if useful else marginal_attempts+1
                best_screenshot_path=item.get('screenshot_path')
                best_quality=quality; best_visual=visual if visual is not None else best_visual; best_retention=retention; stagnant_attempts=0; best_candidate=candidate; best_axe_evidence=axe_evidence; best_lighthouse_evidence=lighthouse_evidence; best_feedback=feedback
                best_rank=rank
            else:
                stagnant_attempts+=1
            agent_runtime.move('decide',number,'Apply deterministic thresholds and rollback ranking')
            decision_skills=agent_runtime.skills_for('decide',enabled=not single_shot)
            iteration_skills=list({skill.id:skill for skill in [*iteration_skills,*decision_skills]}.values())
            total_in+=ti; total_out+=to; total_cost+=cost+wave_cost
            agent_usage=generation_usage or [{"role":"Generator","model":actual_generator,"input_tokens":ti,"output_tokens":to,"cost_usd":cost,"seconds":gen_seconds}]
            agent_usage.extend(diagnosis_usage)
            if number==1: agent_usage.extend(planner_usage)
            for usage_entry in agent_usage:
                generator_role=usage_entry['role']=='Generator' or 'reconstruction agent' in usage_entry['role']
                user_model=usage_entry['model']==run['generator_model']
                usage_entry['reasoning_effort']=pinned_effort if user_model else reasoning_effort(usage_entry['model'],tier)
                usage_entry['reasoning_source']='frozen user selection' if user_model else 'explicit agent configuration'
            # Planning was already charged to the run before validation. Include
            # it in its owning iteration without charging the run a second time.
            iteration_input=sum(int(entry.get("input_tokens") or 0) for entry in agent_usage)
            iteration_output=sum(int(entry.get("output_tokens") or 0) for entry in agent_usage)
            iteration_cost=sum(float(entry.get("cost_usd") or 0) for entry in agent_usage)
            planner_seconds=sum(float(entry.get("seconds") or 0) for entry in planner_usage) if number==1 else 0.0
            diagnosis_seconds=sum(float(entry.get('seconds') or 0) for entry in diagnosis_usage)
            strategy={"representation":"component reconstruction" if reconstruct else "lossless DOM patch","repair_engine":"born-accessible framework reconstruction" if reconstruct else "hybrid evidence-guided program repair","temperature":iteration_temperature,"template":"No page template","template_reason":"Page templates were retired; knowledge is retrieved per detected component.","template_use":"not used","framework_knowledge":{"framework":framework,"components":[item["component"] for item in component_knowledge],"visual_reference":bool(visual_reference)},"patches":{"applied":len(patch_result["applied"]),"skipped":len(patch_result["skipped"]),"deterministic":deterministic_repairs},"model_selection":"Explicit user selection","reasoning_tier":tier,"review_policy":run.get("review_policy") or "automated","evaluation_tools":tools,"content_retention":retention,"content_gate":{"minimum_text_percent":90,"minimum_links_percent":85,"minimum_images_percent":85,"passed":content_pass},"dom_target":float(run.get("max_dom_distance") or 70),"dom_target_enforced":False,"iteration_basis":"Full reconstruction refined from the preceding candidate" if reconstruct and number>1 else "Structured content/media/control inventory plus screenshot" if reconstruct else "Minimal patch from previous candidate and reviewer feedback" if number>1 else "Lossless acquired source","candidate_selection":{"gate_distance":quality,"best_so_far":is_best,"policy":"rollback to the lowest automated-gate distance after a regression"},"taxonomy":{"method":"Fathallah et al. (AccessGuru)","original":source_taxonomy,"candidate":axe_taxonomy(item.get("axe",{}).get("raw_path")),"semantic_assessment":"not_assessed"},"rag":{"enabled":bool(run.get("use_rag")),"activation":"after first measured failure","source":"W3C ACT Rules and source-attributed complementary guidance","retrieved":[{"rule_id":item.get("rule_id"),"rule_name":item.get("rule_name"),"expected":item.get("expected"),"score":item.get("score"),"rule_page":item.get("rule_page"),"source":item.get("source"),"source_kind":item.get("source_kind","official_act")} for item in rag_items]}}
            strategy["candidate_selection"].update({"visual_similarity_percent":visual,"policy":SELECTION_POLICY,'rank':rank,'improvement_basis':last_improvement_basis,'marginal_progress':bool(marginal_attempts)})
            if run.get('model_selection_mode')=='user':
                strategy['model_selection']='User-selected model; no automatic routing or substitution'
            if whole_regeneration:
                strategy['task_preservation']={'missing_native_form_contracts':missing_tasks,'scope':'native action/method/named fields only; dynamic task equivalence not certified'}
                strategy['candidate_selection']['policy']='Automated target distance, missing native form contracts, then content retention; regenerated baseline rollback'
            strategy["generator_evidence_mode"]=evidence_mode
            strategy["reconstruction_mode"]="fragmented" if area_plan else "whole_page" if reconstruct else "not_applicable"
            strategy["area_plan"]=[{"area":item["area"],"id_prefix":item["prefix"]} for item in area_plan]
            strategy["area_checkpoints"]=area_checkpoints
            strategy['frozen_widget_replay']={'version':'captured-widget-adapters-v2','repairs':frozen_widget_repairs,
                                             'runtime_manifest':replay_manifest(candidate)}
            strategy['capture_replay_warnings']=capture_replay_warnings
            strategy['model_configuration']=frozen_choice
            strategy['context_policy']={'version':'current-best-candidate-v1','history_replayed':False,
                                        'state':'best current page, current measured findings and latest feedback'}
            iteration_tool_records=agent_runtime.tools.records[iteration_tool_start:]
            rag_seconds=sum(float(record.get('seconds') or 0) for record in iteration_tool_records
                            if record.get('tool')=='retrieve_accessibility_evidence')
            strategy['stage_accounting']={
                'planning':{'seconds':planner_seconds,'cost_usd':sum(float(entry.get('cost_usd') or 0) for entry in planner_usage) if number==1 else 0.0,'llm_calls':len(planner_usage) if number==1 else 0},
                'diagnosis':{'seconds':diagnosis_seconds,'cost_usd':sum(float(entry.get('cost_usd') or 0) for entry in diagnosis_usage),'llm_calls':len(diagnosis_usage),'mode':'deterministic' if local_generator else diagnosis_policy},
                'generation':{'seconds':gen_seconds,'cost_usd':cost,'llm_calls':len(generation_usage) if generation_usage else 1},
                'rag_retrieval':{'seconds':rag_seconds,'cost_usd':0.0,'examples':len(rag_items),'activated':bool(rag_items)},
                'automated_evaluation':{'seconds':float(item.get('execution_seconds') or 0),'cost_usd':wave_cost,'llm_calls':0}}
            strategy["approach"]={"version":"2026-09-five-approaches-v8","step":approach.step,"name":approach.name,"engine":approach.engine,"instruction":approach.instruction,"inspiration":approach.reference,"reproduction":False}
            strategy['source_view']='network HTML plus uniquely matched captured static placeholders' if response_path.is_file() else 'captured DOM; original network response unavailable'
            strategy['source_hydration']=source_hydration
            strategy["specialist_plan"]=[{k:v for k,v in item.items() if k!="source" and k!="text"} for item in component_plan]
            strategy["extraction_quality"]=source_quality
            strategy['framework_knowledge']['retrieval_method']='detected-component lookup in versioned local library; not semantic-vector retrieval'
            strategy['framework_knowledge']['units']=[{'component':unit['component'],'version':unit.get('knowledge_version'),'source':unit.get('source'),'examples':unit.get('examples',[])} for unit in component_knowledge]
            strategy['target_attainment']={'achieved':bool(metric_pass),'axe_maximum':run['max_axe'],'lighthouse_minimum':run['min_lighthouse'],'wave_aim_minimum':run.get('min_aim'),'result_availability':'retained independently of targets under automated review'}
            strategy['axe_measurements'] = measured_axe
            if actual_generator.startswith('ollama/'):
                strategy['local_llm']={**settings['_local_llm_config'],
                                       'transport':'ollama-native-chat-stream',
                                       'truncate':False,'shift':False}
            if reconstruct: strategy['born_content_contract']={'version':'protected-data-components-v2' if approach.step==5 else 'protected-blocks-v1','layout_owner':'LLM','content_owner':'verified component renderer and frozen-source assembler' if approach.step==5 else 'frozen-source assembler','component_count':len(born_manifest),'renderers':[item['component_renderer'] for item in born_manifest if item.get('component_renderer')],'limitations':['Original application JavaScript is not ported; native forms preserve submission data','Unknown structures retain source semantics; no conformance certification']}
            if reconstruct: strategy['born_framework']=framework_evidence(owned_framework)
            if reconstruct and approach.step==5:
                strategy['born_content_contract']['semantic_composition']={'version':'source-owned-units-v1','unit_count':sum(len(block.get('composition_units',[])) for block in born_manifest),'layout_owner':'LLM internal Bootstrap composition','unknown_structures':'retained as indivisible source-owned units'}
            strategy['patches']['actions']={action:sum(op.get('action')==action for op in patch_result['applied']) for action in {op.get('action') for op in patch_result['applied']}}
            if diagnosis:
                strategy['patch_diagnosis']=diagnosis
            elif single_shot or initial_regeneration or reconstruct:
                strategy['patch_diagnosis']={'status':'not_applicable','reason':'Initial whole-page generation, reconstruction, or single-call baseline; no separate patch diagnosis.'}
            else:
                strategy['patch_diagnosis']={'version':'conditional-grounded-diagnosis-v1','status':'not_called','findings':[],
                    'acceptance_gate':False,'reason':'No stagnation or ambiguous measured evidence triggered an additional LLM diagnosis call.'}
            strategy["resource_quality"]=(item.get("load_metadata") or {}).get("resource_quality") or {}
            strategy['execution_mode']='single_shot' if single_shot else 'iterative'
            if whole_regeneration:
                strategy['execution_mode']=run['execution_mode']
                strategy['design_base']=design_base_evidence
                strategy['regeneration']=regeneration_evidence or {'phase':'localized_refinement','baseline_iteration':1}
                strategy['visual_guidance']={'attached':bool(visual_reference),'source':'best regenerated candidate' if visual_reference else 'none','initial_generation_unchanged':True}
                try: catalogue_support=frozen_choice['temperature_supported']
                except ValueError: catalogue_support=None
                strategy['generation_parameters']={'temperature_requested':iteration_temperature,'temperature_supported_catalogue':catalogue_support,'effective_temperature_confirmed':False,'output_token_ceiling':32000 if initial_regeneration else 4000}
                strategy['representation']='whole-document '+run['transformation_format']+' input' if initial_regeneration else 'localized patch of regenerated HTML'
                strategy['repair_engine']='Content-faithful whole-document prompt; one generation call' if initial_regeneration else 'Localized agent patches with best-candidate rollback'
                strategy['template_use']='page-type '+design_base_evidence['design_name']+' structural reference' if initial_regeneration else 'not used'
                strategy['iteration_basis']='Content-faithful whole-document regeneration' if initial_regeneration else 'Best regenerated candidate; no return to the original source layout'
                strategy['framework_knowledge']={}
                strategy['approach']={'version':(regeneration_evidence or {}).get('version','whole-document-content-faithful-v3'),'step':approach.step,'name':'Whole-page regeneration' if initial_regeneration else 'Localized refinement of regenerated page','engine':'whole_document' if initial_regeneration else 'localized_patch','reproduction':False}
            strategy['reasoning_policy']={'version':'frozen-user-catalog-v1','slider_tier':tier,'generator_requested_effort':pinned_effort,'model_configuration_digest':frozen_choice.get('digest')}
            strategy['baseline']=baseline_evidence
            strategy['resource_contract']={'restored':resource_repairs,'method':'explicit original-resource fallback','limitations':'Resource presence is not semantic/task equivalence'}
            if single_shot:
                strategy['representation']='single-shot HTML response'
                strategy['repair_engine']='Zero-shot prompting; one generation call; no planner, checker feedback, RAG, screenshot or repair postprocessor'
                strategy['approach']={'name':'Zero-shot — single call','engine':'single_shot','inspiration':baseline_evidence['reference'],'reproduction':False}
            strategy["markdown"]={k:v for k,v in (markdown_view or {}).items() if k!="markdown"}
            strategy["rag"]["retrieval_quality"]=rag_quality
            strategy["extraction"]={"method":"frozen HTML plus rendered DOM inventory","reading_order_items":len(inventory["reading_order"]),"inventory_characters":len(json.dumps(inventory,ensure_ascii=False)),"prompt_inventory_limit":180000,"complete_document_text":True,"truncated":False}
            strategy['agentic_runtime']=agent_runtime.snapshot(iteration_skills,iteration_tool_start)
            recorded_call.checkpoint()
            strategy['model_call_evidence']={'schema_version':'model-call-evidence-v1',
                'path':str(output_dir/'model-call-evidence.json'),
                'includes_unevaluated_attempts':True}
            cursor.execute("""INSERT INTO remediation_iterations (run_id,iteration_number,prompt_text,feedback_text,output_path,output_url,decision,decision_reason,generator_provider,generator_model,reviewer_provider,reviewer_model,input_tokens,output_tokens,cost_usd,wave_credits_used,wave_cost_usd,execution_seconds,axe_violations,lighthouse_score,wave_aim_score,candidate_key,screenshot_path,dom_distance,original_dom_nodes,candidate_dom_nodes,dom_changes_json,specialist_reviews_json,agent_usage_json,strategy_json,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",(run_id,number,prompt,feedback,str(path),url,decision,str(decision_data.get("reason") or "")[:8000],actual_generator.split("/",1)[0],actual_generator,actual_reviewer.split("/",1)[0],actual_reviewer,iteration_input,iteration_output,iteration_cost,wave_credits,wave_cost,gen_seconds+diagnosis_seconds+planner_seconds+float(item.get("execution_seconds") or 0),measured_axe['axe_combined_violations'],lighthouse,aim,candidate_key,item.get("screenshot_path"),distance,original_nodes,candidate_nodes,json.dumps(dom_change_summary(source,candidate)),json.dumps([]),json.dumps(agent_usage),json.dumps(strategy),_now(settings)))
            iteration_id=cursor.lastrowid
            persist_metrics(cursor, 'remediation_iterations', iteration_id, measured_axe, item.get('axe', {}).get('raw_path'))
            if axe is not None and lighthouse is not None and (best_measured_rank is None or rank<best_measured_rank):
                best_measured_rank=rank; best_measured_iteration=iteration_id
            executed_iterations+=1
            cursor.execute("UPDATE remediation_runs SET total_input_tokens=%s,total_output_tokens=%s,total_cost_usd=%s,execution_seconds=%s WHERE id=%s",(total_in,total_out,total_cost,time.monotonic()-started,run_id)); conn.commit()
            if decision=="accept": decision_message=f"Candidate {number} accepted: {concise_english_summary(decision_data.get('reason'),420)}"
            elif number < run["max_iterations"]: decision_message=f"Candidate {number} sent to Generator {actual_generator} for {approach.name.lower()} refinement in iteration {number+1}: {concise_english_summary(feedback,420)}"
            else: decision_message=f"Candidate {number} did not satisfy the configured targets/review; the {run['max_iterations']}-iteration limit was reached. Evaluated results remain available: {concise_english_summary(feedback,420)}"
            _event(cursor,conn,run_id,"Acceptance coordinator","decision",decision_message,{"iteration":number,"decision":decision,"generator":actual_generator,"coordinator":actual_reviewer,"failed_categories":decision_data.get("failed_categories") or [],"iteration_cost_usd":iteration_cost})
            if is_best:
                previous_candidate=candidate
            else:
                previous_candidate=best_candidate
                current_axe_evidence=best_axe_evidence; current_lighthouse_evidence=best_lighthouse_evidence
                feedback=rollback_feedback(best_feedback,patch_result['applied'],quality,best_quality)
                continuation=f"iteration {number+1} will resume from the best candidate" if number<run['max_iterations'] else 'the best candidate was retained; no further iteration is available'
                _event(cursor,conn,run_id,"Regression guard","rollback",f"Candidate {number} did not improve the selected objective; {continuation}",{"iteration":number,"candidate_gate_distance":quality,"best_gate_distance":best_quality,'candidate_rank':rank,'best_rank':best_rank,'policy':SELECTION_POLICY})
            if decision=="accept":
                accepted=best_measured_iteration if whole_regeneration else iteration_id
                needs_preservation_refinement=whole_regeneration and preservation_refinement_needed(run.get('execution_mode'),content_pass,missing_tasks)
                if not needs_preservation_refinement or number>=run['max_iterations']: break
                _event(cursor,conn,run_id,'Preservation coordinator','refine','Automated targets achieved; attempting localized content/native-form restoration without adding a rejection gate',{'iteration':number,'missing_native_form_contracts':missing_tasks,'text_retained_percent':retention['text_percent']})
            if stagnant_attempts>=2:
                stop_reason='Refinement plateau reached'
                _event(cursor,conn,run_id,"Budget controller","plateau_stop",f"Stopped after candidate {number}: two consecutive refinements did not improve the best accessibility/visual objective",{"best_gate_distance":best_quality,"best_visual_similarity_percent":best_visual})
                break
            if marginal_attempts:
                stop_reason='Marginal-improvement stop reached'
                _event(cursor,conn,run_id,"Budget controller","marginal_stop",f"Stopped after candidate {number}: the ranking change was below the minimum useful improvement relative to another model call",{"iteration":number,"basis":last_improvement_basis,"candidate_gate_distance":quality,"cost_usd":iteration_cost})
                break
            if number<run['max_iterations']:
                _progress(cursor,conn,run_id,"prompt",round(base+segment*.95),f"Candidate {number} needs refinement; carrying feedback into the next prompt",number)
        if agent_runtime.state != 'complete':
            agent_runtime.move('complete',reason='Iteration loop reached its terminal outcome')
        recorded_call.checkpoint()
        # Thresholds are research targets, not a veto on an evaluated result.
        # Keep the selected candidate usable without claiming targets were met.
        final_status=completion_status(accepted,executed_iterations,run.get('review_policy') or 'automated',automated_achieved)
        final_message=("Candidate accepted and retained as a remediation result" if accepted else f'{stop_reason}; no executable candidate was evaluated' if not executed_iterations else "Automated thresholds were achieved, but the selected review gate was not satisfied" if automated_achieved else f"{stop_reason}; automated accessibility thresholds were not achieved")
        if not accepted and executed_iterations and run.get('review_policy') == 'automated':
            if best_measured_iteration:
                accepted=best_measured_iteration
                final_status='completed_with_warnings'
                final_message=f"{stop_reason}; evaluated result retained and available. Targets not reached: Axe <= {run['max_axe']}, Lighthouse >= {run['min_lighthouse']}" + (f", WAVE AIM >= {run['min_aim']}" if run.get('use_wave') else '')
        cursor.execute("UPDATE remediation_runs SET status=%s,current_phase='complete',progress_percent=100,progress_message=%s,progress_updated_at=%s,accepted_iteration_id=%s,total_input_tokens=%s,total_output_tokens=%s,total_cost_usd=%s,execution_seconds=%s,completed_at=%s WHERE id=%s",(final_status,_bounded_progress(final_message),_now(settings),accepted,total_in,total_out,total_cost,time.monotonic()-started,_now(settings),run_id)); conn.commit(); _event(cursor,conn,run_id,"Acceptance coordinator","complete",final_message,{"status":final_status,"iterations":executed_iterations,"total_cost_usd":total_cost})
    except Exception as error:
        conn.rollback()
        error_text = str(error).strip() or type(error).__name__
        retained=retain_interrupted_result(best_measured_iteration,run.get('review_policy') or 'automated',isinstance(error,requests.RequestException))
        if retained:
            message=f"Refinement interrupted by provider/network error; best evaluated candidate retained. {error_text}"
            cursor.execute("UPDATE remediation_runs SET status='completed_with_warnings',current_phase='complete',progress_percent=100,progress_message=%s,error_message=%s,accepted_iteration_id=%s,execution_seconds=%s,completed_at=%s WHERE id=%s",(_bounded_progress(message),error_text,best_measured_iteration,time.monotonic()-started,_now(settings),run_id))
        else:
            message=f"Remediation stopped: {error_text}"
            cursor.execute("UPDATE remediation_runs SET status='failed',current_phase='failed',progress_message=%s,error_message=%s,execution_seconds=%s,completed_at=%s WHERE id=%s",(_bounded_progress(message),error_text,time.monotonic()-started,_now(settings),run_id))
        conn.commit()
        try: _event(cursor,conn,run_id,"System","refinement_interrupted" if retained else "failed",message,{'traceback':traceback.format_exc(limit=8),'retained_iteration':best_measured_iteration if retained else None,'agentic_runtime':agent_runtime.snapshot()})
        except Exception: conn.rollback()
    finally: cursor.close(); conn.close()
