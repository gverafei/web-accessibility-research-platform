"""Single-call HTML baseline inspired by Delnevo et al., CCNC 2024.

The paper studies snippets with GPT-3.5, not whole contemporary pages. This
adapter starts with its question and requests a complete full-page correction;
full-page/model/prompt differences are recorded explicitly.
No checker evidence, RAG, screenshot, planner or repair postprocessor is sent.
"""
import re
from remediation_content_contract import original_page_wrapper

REFERENCE='https://doi.org/10.1109/CCNC51664.2024.10454680'


def baseline_prompt(source):
    if len(source)>180000:
        raise ValueError('Single-shot source exceeds the context allowance; no truncated HTML was submitted')
    return ('Is the following HTML code accessible?\n'
            'For this full-page adaptation, briefly assess it and provide one complete corrected HTML document in a fenced html block. '
            'Preserve all source text, destinations, images, form controls and tasks. Do not return only a suggested snippet.\n'
            'Correct the supplied content directly. Do not embed or redirect to the original page in an iframe as a substitute for remediation.\n'
            +source)


def baseline_candidate(response, source, base_url=None):
    blocks=re.findall(r'```(?:html)?\s*\n(.*?)```',response,re.S|re.I)
    complete=[block.strip() for block in blocks if re.search(r'<html\b',block,re.I) and re.search(r'</html\s*>',block,re.I)]
    if not blocks:
        match=re.search(r'(<!doctype\s+html[^>]*>\s*)?<html\b.*?</html\s*>',response,re.S|re.I)
        if match: complete=[match.group(0)]
    if len(complete)==1:
        if original_page_wrapper(complete[0],source,base_url):
            return source,{'output':'original retained: embedding the unchanged original is not a full-page correction','reference':REFERENCE,'reproduction':False}
        return complete[0],{'output':'complete HTML proposed','reference':REFERENCE,'reproduction':False}
    # Never substitute a small suggested snippet for an entire real page.
    return source,{'output':'original retained: no unique complete HTML replacement supplied','reference':REFERENCE,'reproduction':False}
