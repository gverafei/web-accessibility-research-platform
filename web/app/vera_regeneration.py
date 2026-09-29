"""Whole-document regeneration followed by localized repair, not slot assembly."""
import hashlib
import re
from collections import Counter
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from html.parser import HTMLParser
from vera_prompt import SYSTEM_PROMPT, REFINED_INSTRUCTION, PROMPT_VERSION
from regeneration_references import select_reference, reference_instruction
from remediation_content_contract import original_page_wrapper

PROMPT_SOURCE='https://github.com/gverafei/conceptual-model/blob/main/conceptual-model.ipynb'
MODES={'regenerate_only','regenerate_refine'}


def preservation_refinement_needed(mode, content_pass, missing_tasks):
    """Continuation advice, never an additional result-rejection gate."""
    return mode=='regenerate_refine' and (not content_pass or bool(missing_tasks))


def generation_messages(content, root_url, *, reference_document=None, framework='bootstrap'):
    if not content.strip(): raise ValueError('Regeneration input is empty')
    if len(content)>180000: raise ValueError('Regeneration input exceeds its allowance; no truncated input submitted')
    messages=[{'role':'system','content':SYSTEM_PROMPT+REFINED_INSTRUCTION},
              {'role':'user','content':f"Use the following content to create a new accessible web page version. The root URL is '{root_url}'."},
              {'role':'user','content':content}]
    from regeneration_references import DESIGN_BASES
    if framework not in DESIGN_BASES: raise ValueError('Unsupported regeneration design base')
    from regeneration_components import component_instruction
    messages[0]['content'] += '\nMANDATORY DESIGN BASE: '+DESIGN_BASES[framework][0]+'. Include the exact stylesheet '+DESIGN_BASES[framework][1]+'. This selection overrides Bootstrap-specific advice above. Do not mix frameworks. Retain the selected base during refinements.\n'+component_instruction(framework)
    reference=select_reference(reference_document if reference_document is not None else content,framework)
    messages.extend([{'role':'user','content':reference_instruction(reference)},{'role':'user','content':reference['html']}])
    return messages


def generation_evidence(messages, representation, source_provider, temperature=.5):
    reference_metadata=None
    if len(messages)==5 and messages[3]['content'].startswith('PAGE_REFERENCE_METADATA: '):
        import json
        reference_metadata=json.loads(messages[3]['content'].split('\n',1)[0].removeprefix('PAGE_REFERENCE_METADATA: '))
    return {'version':PROMPT_VERSION,'prompt_source':PROMPT_SOURCE,
            'structural_reference_metadata':reference_metadata,
            'system_prompt_sha256':hashlib.sha256(messages[0]['content'].encode()).hexdigest(),
            'literal_system_prompt_sha256':hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
            'input_sha256':hashlib.sha256(messages[2]['content'].encode()).hexdigest(),
            'representation':representation,'source_provider':source_provider,
            'structural_reference':len(messages)==5,'temperature':float(temperature),
            'messages':messages}


class _DocumentBoundaries(HTMLParser):
    """Locate actual document tags, ignoring lookalikes in scripts/comments."""
    def __init__(self, source):
        super().__init__()
        self.source=source
        self.lines=source.splitlines(keepends=True)
        self.doctypes=[]; self.roots=[]; self.ends=[]

    def source_offset(self):
        line,column=self.getpos()
        return sum(len(value) for value in self.lines[:line-1])+column

    def handle_decl(self, declaration):
        if re.match(r'doctype\s+html\b',declaration,re.I): self.doctypes.append(self.source_offset())

    def handle_starttag(self, tag, attrs):
        if tag=='html': self.roots.append(self.source_offset())

    def handle_endtag(self, tag):
        offset=self.source_offset()
        if tag=='html' and self.source[offset:offset+2]=='</':
            self.ends.append(self.source.index('>',offset)+1)


def complete_candidate(response, original, root_url):
    # Extract, never repair: a complete page remains valid when the model adds
    # explanatory prose outside it. Ambiguous or truncated documents still fail.
    boundaries=_DocumentBoundaries(response)
    boundaries.feed(response); boundaries.close()
    if not (len(boundaries.doctypes)==len(boundaries.roots)==len(boundaries.ends)==1
            and boundaries.doctypes[0]<boundaries.roots[0]<boundaries.ends[0]):
        raise ValueError('Regeneration output must be complete HTML, not an assessment or fragment. The response may have been cut off by the output-token limit; an incomplete page cannot be evaluated.')
    candidate=response[boundaries.doctypes[0]:boundaries.ends[0]].strip()
    if original_page_wrapper(candidate,original,root_url):
        raise ValueError('Regeneration cannot substitute an embedded unchanged original')
    return candidate


def omission_context(original, candidate, root_url):
    """Exact acquired text/resources for localized restoration, never old CSS."""
    source=BeautifulSoup(original,'html.parser'); proposed=BeautifulSoup(candidate,'html.parser')
    words=lambda text:Counter(re.findall(r'\w+',text.casefold()))
    remaining=words(proposed.get_text(' ',strip=True)); missing=[]
    for node in source.select('p,li'):
        text=node.get_text(' ',strip=True); required=words(text)
        if sum(required.values())<12: continue
        if sum((required-remaining).values())<=sum(required.values())*.1: continue
        missing.append({'text':text,'destinations':[urljoin(root_url,a['href']) for a in node.select('a[href]')]})
    return missing


def resource_omissions(original, candidate, root_url):
    """Exact missing destinations/media, independent of mutable loop feedback."""
    source=BeautifulSoup(original,'html.parser'); proposed=BeautifulSoup(candidate,'html.parser')
    def durable_href(node):
        href=(node.get('href') or '').strip()
        return bool(href) and not href.lower().startswith(('#','javascript:'))
    def image_url(node):
        src=(node.get('src') or '').strip()
        return urljoin(root_url,src) if src and not src.lower().startswith('data:') else ''
    destinations={urljoin(root_url,node['href'].strip()) for node in proposed.select('a[href]') if durable_href(node)}
    media={image_url(node) for node in proposed.select('img[src]') if image_url(node)}
    links=[]; images=[]; seen_links=set(); seen_images=set()
    for node in source.select('a[href]'):
        if not durable_href(node): continue
        url=urljoin(root_url,node['href'].strip()); text=node.get_text(' ',strip=True)
        image=node.select_one('img[src]')
        linked_image_url=image_url(image) if image else ''
        identity=(url,text,linked_image_url)
        if url in destinations or identity in seen_links: continue
        seen_links.add(identity)
        evidence={'url':url,'text':text,'title':node.get('title','')}
        if linked_image_url: evidence['image_src']=linked_image_url
        links.append(evidence)
    for node in source.select('img[src]'):
        url=image_url(node)
        if not url: continue
        if url in media or url in seen_images: continue
        seen_images.add(url)
        evidence={'url':url,'alt':node.get('alt',''),'title':node.get('title','')}
        link=node.find_parent('a',href=True)
        if link: evidence['link_destination']=urljoin(root_url,link['href'])
        images.append(evidence)
    return {'links':links,'images':images}


def task_omissions(original, candidate, root_url):
    """Missing native form contracts; no invented interactions or old styling."""
    source=BeautifulSoup(original,'html.parser'); proposed=BeautifulSoup(candidate,'html.parser')
    missing=[]
    for form in source.select('form'):
        action=urljoin(root_url,form.get('action','')); method=form.get('method','get').lower()
        fields=[{'name':n['name'],'type':n.get('type',n.name),'value':n.get('value','')} for n in form.select('input[name],select[name],textarea[name],button[name]')]
        if not fields: continue
        required={n['name'] for n in fields}
        matches=[f for f in proposed.select('form') if urljoin(root_url,f.get('action',''))==action and f.get('method','get').lower()==method]
        if not any(required<={n['name'] for n in f.select('[name]')} for f in matches):
            missing.append({'action':action,'method':method,'fields':fields})
    return missing
