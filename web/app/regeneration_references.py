"""Small, offline page exemplars. Content remains owned by the acquisition.

Selection is deliberately explainable, not an LLM or vector similarity claim.
These original skeletons are guidance, never conformance-certified templates.
"""
import hashlib
import json
from bs4 import BeautifulSoup
from regeneration_components import component_instruction

VERSION = 'page-exemplars-v2'
DESIGN_BASES = {
    'bootstrap': ('Bootstrap 5.3.8', 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css'),
    'pico': ('Pico CSS 2.1.1', 'https://cdn.jsdelivr.net/npm/@picocss/pico@2.1.1/css/pico.min.css'),
    'bulma': ('Bulma 1.0.4', 'https://cdn.jsdelivr.net/npm/bulma@1.0.4/css/bulma.min.css'),
}
FRAMEWORK_SELECTIONS = {'vera_reference': 'bootstrap', 'pico_reference': 'pico', 'bulma_reference': 'bulma'}


def selected_framework(selection):
    return FRAMEWORK_SELECTIONS.get(selection, 'bootstrap')
ROOT = 'https://getbootstrap.com/docs/5.3/'
EXAMPLES = {
    'homepage': ('examples/heroes/', '<section class="py-4"><h1>{{ACQUIRED_PAGE_TITLE}}</h1>{{ALL_ORIGINAL_HERO_CONTENT}}</section><div class="row g-4"><section class="col-12 col-md-6">{{ORIGINAL_CONTENT_GROUP}}</section></div>'),
    'listing': ('examples/album/', '<h1>{{ACQUIRED_PAGE_TITLE}}</h1><div class="row row-cols-1 row-cols-md-2 g-4"><div class="col"><article class="card h-100"><img class="card-img-top img-fluid" src="{{ACQUIRED_IMAGE_URL}}" alt="{{SOURCE_SUPPORTED_ALT}}"><div class="card-body"><h2 class="h4"><a href="{{ACQUIRED_ITEM_URL}}">{{ACQUIRED_ITEM_TITLE}}</a></h2>{{COMPLETE_ITEM_CONTENT_AND_METADATA}}</div></article></div></div>'),
    'article': ('examples/blog/', '<article class="mx-auto" style="max-width:75ch"><header><h1>{{ACQUIRED_ARTICLE_TITLE}}</h1>{{ORIGINAL_AUTHOR_AND_DATE}}</header>{{ALL_ORIGINAL_PARAGRAPHS_HEADINGS_FIGURES_AND_LINKS_IN_ORDER}}</article>'),
    'form': ('forms/overview/', '<h1>{{ACQUIRED_PAGE_TITLE}}</h1>{{ORIGINAL_CONTEXT}}<form action="{{ORIGINAL_ACTION}}" method="{{ORIGINAL_METHOD}}"><fieldset><legend>{{ORIGINAL_GROUP_LABEL}}</legend><label class="form-label" for="example-field">{{ORIGINAL_FIELD_LABEL}}</label><input class="form-control" id="example-field" name="{{ORIGINAL_FIELD_NAME}}" type="{{ORIGINAL_FIELD_TYPE}}">{{ALL_REMAINING_FIELDS_OPTIONS_HIDDEN_TOKENS_HELP_AND_ERRORS}}<button class="btn btn-primary" type="submit">{{ORIGINAL_SUBMIT_LABEL}}</button></fieldset></form>'),
    'data': ('content/tables/', '<h1>{{ACQUIRED_PAGE_TITLE}}</h1>{{ORIGINAL_CONTEXT}}<div class="table-responsive" role="region" aria-label="{{ORIGINAL_TABLE_LABEL}}" tabindex="0"><table class="table"><caption>{{ORIGINAL_CAPTION}}</caption><thead><tr><th scope="col">{{ORIGINAL_COLUMN_HEADING}}</th></tr></thead><tbody>{{ALL_ORIGINAL_ROWS_CELLS_AND_HEADER_RELATIONSHIPS}}</tbody></table></div>'),
}


def select_reference(document, framework='bootstrap'):
    if framework not in DESIGN_BASES:
        raise ValueError('Unsupported regeneration design base')
    soup = BeautifulSoup(document, 'html.parser')
    main = soup.find('main') or soup.body or soup
    controls = [field for field in main.select('form input, form select, form textarea')
                if field.get('type', '').lower() not in {'hidden', 'submit', 'button', 'search'}
                and field.get('name', '').lower() not in {'q', 'query', 'search', 's'}]
    rows = len(main.select('table tr'))
    articles = len(main.find_all('article'))
    paragraphs = len(main.find_all('p'))
    cards = len(main.select('.card, [itemtype*="Product"], [itemtype*="NewsArticle"]'))
    features = dict(non_search_form_fields=len(controls), table_rows=rows,
                    articles=articles, paragraphs=paragraphs, cards=cards)
    if len(controls) >= 2: kind, reason = 'form', 'multiple non-search fields in the main content'
    elif rows >= 3: kind, reason = 'data', 'a substantive table in the main content'
    elif articles >= 3 or cards >= 3: kind, reason = 'listing', 'repeated article/card items'
    elif articles == 1 and paragraphs >= 4: kind, reason = 'article', 'one article with multiple paragraphs'
    else: kind, reason = 'homepage', 'mixed or uncertain structure; general-purpose fallback'
    path, body = EXAMPLES[kind]
    html = ('<!doctype html><html lang="{{SOURCE_LANGUAGE}}"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>{{ACQUIRED_PAGE_TITLE}}</title>'
            '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css">'
            '<style>a{color:#0645ad}a:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid #111;outline-offset:3px}img{max-width:100%;height:auto}footer svg{width:1.25em;height:1.25em}</style>'
            '</head><body><a class="visually-hidden-focusable" href="#content">{{LOCALIZED_SKIP_LABEL}}</a>'
            '<header class="border-bottom py-3"><div class="container"><nav aria-label="{{ORIGINAL_NAVIGATION_LABEL}}" class="navbar"><ul class="nav flex-wrap"><li class="nav-item"><a class="nav-link" href="{{ACQUIRED_NAVIGATION_URL}}">{{ACQUIRED_NAVIGATION_TEXT}}</a></li></ul></nav></div></header>'
            '<main id="content" class="container py-4">'+body+'</main>'
            '<footer class="border-top py-4"><div class="container">{{ALL_ORIGINAL_FOOTER_GROUPS_CONTACTS_LEGAL_AND_SOCIAL_LINKS}}</div></footer></body></html>')
    if framework in {'pico', 'bulma'}:
        # Adapt the semantic exemplar, not acquired page content. Pico styles
        # native HTML; Bootstrap classes must not leak into its reference.
        example=BeautifulSoup(html,'html.parser')
        example.html['data-theme']='light'
        example.find('link',rel='stylesheet')['href']=DESIGN_BASES[framework][1]
        for node in example.select('[class]'):
            classes=node.get('class',[])
            mapped=[]
            if framework == 'bulma':
                mapping={'container':['container'],'row':['columns','is-multiline'],
                         'col':['column','is-12-mobile','is-half-desktop'],
                         'col-12':['column','is-12-mobile','is-half-desktop'],
                         'card':['card'],'card-body':['card-content'],
                         'table-responsive':['table-container'],'table':['table'],
                         'form-label':['label'],'form-control':['input'],
                         'btn':['button'],'btn-primary':['is-link'],'navbar':['navbar'],
                         'nav':['is-flex','is-flex-wrap-wrap'],'nav-link':['navbar-item']}
                for cls in classes: mapped.extend(mapping.get(cls,[]))
                if node.name == 'h1': mapped.extend(['title','is-2'])
                if node.name == 'h2': mapped.extend(['title','is-4'])
            else:
                if 'container' in classes: mapped.append('container')
                if 'row' in classes: mapped.append('grid')
                if 'table-responsive' in classes: mapped.append('overflow-auto')
            if 'visually-hidden-focusable' in classes: mapped.append('skip-link')
            if mapped: node['class']=mapped
            else: del node['class']
        example.style.string += '.skip-link{position:absolute;left:-10000px}.skip-link:focus{position:static}@media(max-width:576px){.grid{grid-template-columns:1fr}}'
        if framework == 'bulma':
            example.style.string += '.column{min-width:0}a{overflow-wrap:anywhere}main{overflow-wrap:anywhere}'
        html=str(example)
    return dict(version=VERSION, framework=framework, design_name=DESIGN_BASES[framework][0], stylesheet=DESIGN_BASES[framework][1], page_type=kind, reason=reason, features=features,
                html=html, sha256=hashlib.sha256(html.encode()).hexdigest(),
                sources=[ROOT+path, ROOT+'getting-started/accessibility/', ROOT+'components/navbar/', ROOT+'components/modal/', ROOT+'components/accordion/'] if framework=='bootstrap' else (['https://bulma.io/documentation/start/installation/','https://bulma.io/documentation/components/card/','https://bulma.io/documentation/components/navbar/'] if framework=='bulma' else ['https://picocss.com/docs','https://picocss.com/docs/grid']),
                provenance='Original locally curated illustrative skeleton; not a fetched official full-page example',
                certified_accessible=False)


def reference_instruction(reference):
    metadata = {key: reference[key] for key in ('version', 'framework', 'design_name', 'stylesheet', 'page_type', 'reason', 'features', 'sha256', 'sources', 'provenance')}
    return ('PAGE_REFERENCE_METADATA: '+json.dumps(metadata, ensure_ascii=False)+'\n'
            'Use the following '+reference['design_name']+' skeleton only as visual/semantic guidance, not content or a required layout. '
            'The selected design base is REQUIRED: include its exact stylesheet URL '+reference['stylesheet']+'. Do not mix frameworks. '
            'Replace every {{...}} marker with acquired material or omit an unsupported example block. '
            'Never publish example labels, invented links, products, forms or placeholder images. '
            'Preserve ALL source groups, even those absent from this example. For mixed pages combine appropriate structures; '
            'the inferred page type is a hint, not an instruction to discard other content.\n'
            + component_instruction(reference['framework']))


def ensure_design_base(document, framework):
    """Enforce the CSS dependency, not visual quality or component correctness."""
    if framework not in DESIGN_BASES: raise ValueError('Unsupported regeneration design base')
    soup=BeautifulSoup(document,'html.parser')
    if soup.head is None: raise ValueError('Regenerated page needs a head for its design base')
    required=DESIGN_BASES[framework][1]
    changes=[]
    for link in list(soup.select('link[rel="stylesheet"]')):
        href=link.get('href','')
        is_framework=any(name in href.lower() for name in ('bootstrap','picocss','bulma'))
        if is_framework and href!=required:
            changes.append({'action':'removed_conflicting_framework_stylesheet','url':href})
            link.decompose()
    if not any(link.get('href')==required for link in soup.select('link[rel="stylesheet"]')):
        link=soup.new_tag('link',rel='stylesheet',href=required)
        soup.head.insert(0,link)
        changes.append({'action':'added_required_framework_stylesheet','url':required})
    if framework == 'bootstrap' and soup.select('[data-bs-toggle], [data-bs-dismiss], [data-bs-ride]'):
        from regeneration_components import BOOTSTRAP_BUNDLE
        scripts=list(soup.select('script[src]'))
        for script in scripts:
            src=script.get('src','')
            if 'bootstrap' in src.lower() and src != BOOTSTRAP_BUNDLE:
                changes.append({'action':'removed_conflicting_bootstrap_script','url':src})
                script.decompose()
        matches=soup.select('script[src="'+BOOTSTRAP_BUNDLE+'"]')
        for duplicate in matches[1:]:
            duplicate.decompose()
            changes.append({'action':'removed_duplicate_bootstrap_bundle','url':BOOTSTRAP_BUNDLE})
        if not matches:
            script=soup.new_tag('script',src=BOOTSTRAP_BUNDLE)
            (soup.body or soup.head).append(script)
            changes.append({'action':'added_required_behavior_bundle','url':BOOTSTRAP_BUNDLE})
    return str(soup),dict(framework=framework,design_name=DESIGN_BASES[framework][0],stylesheet=required,changes=changes)
