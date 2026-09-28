"""Small compatibility hints for historical fragmented reconstruction runs.

The former detailed Bootstrap collection has been retired. Current whole-page
regeneration uses regeneration_references and regeneration_components instead;
this helper remains only for historical execution modes.
"""

import re


COMPONENTS = {
    "navigation": {
        "signals": ("nav", "menu", "navbar"),
        "bootstrap": "Use <nav aria-label=\"Primary\"> with a real list of links. Bootstrap .navbar may style it; a collapsed menu needs a button with aria-controls and aria-expanded plus bootstrap.bundle.min.js. Preserve every link and its order.",
        "tailwind": "Use semantic <nav aria-label=\"Primary\"><ul>…</ul></nav>. Tailwind supplies styling only: implement the disclosure button with aria-expanded/aria-controls and a small keyboard-operable script; never use clickable divs.",
    },
    "hero": {
        "signals": ("hero", "banner", "masthead", "carousel", "slider"),
        "bootstrap": "Represent the hero as a labelled <section>. Prefer a static list of ALL acquired slides when rotation is not essential. If Carousel is retained, provide pause/play, labelled previous/next buttons, no forced autoplay, and bootstrap.bundle.min.js. Stop rotation on keyboard focus and pointer hover; it must not restart without explicit user action. Do not move keyboard focus when changing slides. Keep every background/image, caption, destination and call to action; Bootstrap styling alone is not accessibility.",
        "tailwind": "Build a labelled semantic section with the original image, heading, text, and calls to action. For a carousel, use native buttons, an announced slide status, pause control, keyboard operation, and reduced-motion handling.",
    },
    "cards": {
        "signals": ("card", "teaser", "tile", "news", "product", "article"),
        "bootstrap": "Use <article class=\"card\"> per independent item, one descriptive link target, logical headings, and .img-fluid with meaningful alt text. Do not duplicate links or truncate titles/content.",
        "tailwind": "Use <article> per independent item with visible focus styles, logical headings, responsive grid utilities, and meaningful image alternatives. Preserve every item and destination.",
    },
    "forms": {
        "signals": ("form", "input", "select", "textarea", "search"),
        "bootstrap": "Use explicit <label for>, .form-control/.form-select, fieldset/legend for groups, programmatic errors with aria-describedby, and a real submit button. Keep names, values, action, method, and validation behavior.",
        "tailwind": "Use native controls with explicit labels, fieldset/legend, programmatic help/errors, visible focus rings, and adequate targets. Utilities never replace accessible names or native behavior.",
    },
    "tables": {
        "signals": ("table", "thead", "tbody"),
        "bootstrap": "Keep genuine tabular data in <table> with <caption>, scoped headers, and .table-responsive on an externally labelled region; never turn rows into visual cards if relationships would be lost.",
        "tailwind": "Keep genuine tabular data in a semantic table with caption and scoped headers. Put horizontal overflow on a labelled wrapper, not on the table semantics.",
    },
    "lists": {
        "signals": ("listing", "list", "pagination", "results"),
        "bootstrap": "Use ul/ol for collections and <nav aria-label=\"Pagination\"> for paging. Mark the current page with aria-current=\"page\" and retain filters, counts, and every result.",
        "tailwind": "Use semantic lists and a labelled pagination nav. Preserve counts, filters, result metadata, all destinations, keyboard focus, and a clear current-page state.",
    },
    "disclosure": {
        "signals": ("accordion", "collapse", "details", "modal", "dialog"),
        "bootstrap": "Prefer native details/summary for simple disclosure. Bootstrap accordion/modal controls need unique ids, accurate aria-expanded/aria-controls, focus return, Escape handling, and bootstrap.bundle.min.js.",
        "tailwind": "Prefer details/summary. Custom dialogs need a labelled native <dialog> or full focus management, Escape dismissal, focus return, and inert background; Tailwind supplies no behavior.",
    },
    "media": {
        "signals": ("img", "picture", "video", "audio", "figure"),
        "bootstrap": "Preserve meaningful media URLs. Use .img-fluid, width/height where known, empty alt only for truly decorative images, figure/figcaption when a caption exists, and captions/transcripts for timed media.",
        "tailwind": "Preserve meaningful media URLs and aspect ratio. Use responsive sizing, context-derived alt text, empty alt only for decorative images, captions, and timed-media alternatives.",
    },
    "footer": {
        "signals": ("footer",),
        "bootstrap": "Use one <footer> with grouped navigation labels, contact/address semantics where appropriate, and every original legal/social destination.",
        "tailwind": "Use a semantic footer with labelled navigation groups, readable contrast and focus, and every original legal/social destination.",
    },
}

# Small executable references, not full-page templates. Replace placeholders
# with the acquired content; never publish placeholder labels/destinations.
PATTERNS = {
    "navigation": '<nav aria-label="PRIMARY LABEL"><ul><li><a href="EXACT ACQUIRED URL">ORIGINAL TEXT</a></li><li><details><summary>ORIGINAL GROUP LABEL</summary><ul><li><a href="EXACT ACQUIRED URL">ORIGINAL CHILD TEXT</a></li></ul></details></li></ul></nav>',
    "hero": '<section aria-labelledby="LOCAL-ID"><h2 id="LOCAL-ID">ORIGINAL LABEL</h2><ul class="list-unstyled"><li><figure><img class="img-fluid" src="EXACT SLIDE URL" alt="CONTEXTUAL ALTERNATIVE"><figcaption>ORIGINAL CAPTION AND LINKS</figcaption></figure></li><!-- repeat EVERY acquired slide, not just the visible one --></ul></section>',
    "forms": '<form action="ORIGINAL ACTION" method="ORIGINAL METHOD"><fieldset><legend>ORIGINAL GROUP LABEL</legend><label for="LOCAL-ID">ORIGINAL FIELD LABEL</label><input id="LOCAL-ID" name="ORIGINAL NAME" type="ORIGINAL TYPE"><button type="submit">ORIGINAL SUBMIT TEXT</button></fieldset></form>',
    "disclosure": '<details><summary>ORIGINAL LABEL</summary><div>COMPLETE ORIGINAL DISCLOSED CONTENT</div></details>',
    "media": '<figure><img class="img-fluid" src="EXACT ACQUIRED URL" alt="ALTERNATIVE BASED ON IMAGE AND CONTEXT"><figcaption>ORIGINAL CAPTION WHEN PRESENT</figcaption></figure>',
}


def component_reference(name,framework='bootstrap'):
    if name=="hero": return "https://www.w3.org/WAI/tutorials/carousels/"
    if name=="forms": return "https://www.w3.org/WAI/tutorials/forms/"
    if framework=='tailwind': return 'https://www.w3.org/WAI/ARIA/apg/patterns/'
    return "https://getbootstrap.com/docs/5.3/getting-started/accessibility/"


def retrieve_framework_knowledge(inventory, framework="bootstrap"):
    haystack=" ".join(inventory.get("signals", [])).casefold()
    selected=[]
    for name,item in COMPONENTS.items():
        if any(re.search(r'(?<![a-z0-9])'+re.escape(signal)+r'(?![a-z0-9])',haystack) for signal in (*item["signals"],name)):
            selected.append({"component":name,"guidance":item[framework],"source":component_reference(name,framework),"pattern":PATTERNS.get(name),"contract":"Preserve original text/assets/destinations; no placeholders; test keyboard, focus, names and contrast","knowledge_version":"2026-09-component-contracts-v2","provenance":"Manually curated component guidance; source link is not a live documentation retrieval or a conformance certificate"})
    if not selected:
        selected=[{"component":"document","guidance":"Use a complete semantic document with skip link, labelled landmarks, one meaningful h1, logical headings, visible focus, reflow, and preserved content/tasks."}]
    return selected
