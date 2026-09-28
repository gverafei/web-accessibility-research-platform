"""Curated dependency/interaction contracts, not WCAG-certified components.

Examples are advisory: only instantiate components justified by source tasks.
"""
BOOTSTRAP_BUNDLE = 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js'
BOOTSTRAP_PATTERNS = '''
BOOTSTRAP INTERACTION CONTRACT (5.3.8): CSS does not implement behaviors.
For data-bs-toggle collapse, dropdown, modal, offcanvas, tab/pill, carousel,
or dismiss controls include bootstrap.bundle.min.js exactly once before closing
body (bundle includes Popper; no jQuery). Do not combine other Bootstrap versions.
Example responsive navigation (replace all markers and keep all original links):
<nav class="navbar navbar-expand-lg" aria-label="{{SOURCE_NAV_LABEL}}">
<div class="container"><button class="navbar-toggler" type="button"
data-bs-toggle="collapse" data-bs-target="#site-navigation"
aria-controls="site-navigation" aria-expanded="false"
aria-label="{{LOCALIZED_TOGGLE_LABEL}}"><span class="navbar-toggler-icon"></span></button>
<div class="collapse navbar-collapse" id="site-navigation"><ul class="navbar-nav">
<li class="nav-item"><a class="nav-link" href="{{SOURCE_URL}}">{{SOURCE_LABEL}}</a></li>
</ul></div></div></nav>
With scripts unavailable, essential navigation/content must remain reachable;
provide a noscript CSS fallback revealing .collapse.navbar-collapse and hiding
its toggler, or use always-visible wrapping navigation instead.
Example disclosure when the source actually has expandable content:
<h2><button class="accordion-button collapsed" type="button" data-bs-toggle="collapse"
data-bs-target="#source-panel" aria-controls="source-panel" aria-expanded="false">
{{SOURCE_HEADING}}</button></h2><div class="accordion-collapse collapse" id="source-panel">
<div class="accordion-body">{{COMPLETE_SOURCE_PANEL}}</div></div>
Native details/summary is simpler when group coordination is unnecessary.
Do not assert extra arrow/Home/End accordion keyboard behavior without implementing
and testing it. Tab and Enter/Space must work with native buttons.
Modal only for a real source dialog task: trigger is a button targeting a unique
id; dialog has tabindex=-1, aria-labelledby referencing its visible title,
an explicitly named data-bs-dismiss="modal" close button. Keep Escape enabled.
Bootstrap manages focus; focus a meaningful field on shown.bs.modal if needed,
not the autofocus attribute; verify focus return to trigger after close. Do not
hide essential source information exclusively in a dialog. Do not invent dialogs.
Dropdowns need real button toggles with aria-expanded; ordinary site links are
not application role=menu/menuitem widgets. Tabs require linked tab/panel IDs,
selected states and tested keyboard behavior; prefer headings and visible sections
if tabs are not needed. Never enable carousel autoplay; preserve every slide and
caption as static content when that better supports screen-reader access.
Audit target IDs, script loading, state updates, keyboard opening/closing, focus,
320px reflow and script-disabled access. Static code alone does not prove usability.
'''

BULMA_PATTERNS = '''
BULMA 1.0.4 CONTRACT: a CSS-only library, no built-in JavaScript behavior.
Use .section > .container, .columns.is-multiline > .column.is-12-mobile.is-4-desktop,
.card > .card-image + .card-content, .title/.subtitle/.content, .field > .label
+ .control > .input/.textarea, .button, and .table-container > .table.
Labels must be native label elements with matching for/id. Preserve original
form action/method, names, options and hidden fields; never invent a working backend.
Do not copy Bootstrap row/col/btn/form-control/data-bs attributes or Bootstrap JS.
CRITICAL WIDTH RULE: never combine unqualified is-12/is-full with fractional
is-5-tablet/is-half-desktop etc. The unqualified full width overrides breakpoint
widths and can make two columns each 100%, overflowing a non-wrapping row.
Use is-12-mobile (not is-12), is-5-tablet / is-7-tablet for a two-column hero;
use is-12-mobile / is-4-desktop for three cards, and is-multiline where wrapping
is needed. Put min-width:0 on flex children, max-width:100%;height:auto on images,
overflow-wrap:anywhere on long text/links. No overflow-x:hidden to conceal failures.
Keep hero images reasonably bounded; do not create giant square above-fold banners.
Make inline text links visibly underlined; class colors alone may erase the cue.
Prefer wrapping, always-visible nav links with native landmarks. If a burger is
needed, use a native button with aria-controls/aria-expanded and explicit local
JavaScript toggling is-active on both button and matching navbar-menu, updating
aria-expanded. CSS alone will not open it. Provide a script-disabled visible menu.
For expandable content use details/summary. For dialogs prefer native dialog with
showModal(), explicitly named close button, Escape/focus-return handling and tests;
Bulma modal/is-active classes alone do not provide focus trapping or semantics.
Use responsive image sizing; do not enlarge tiny acquired thumbnails into banners.
Theme/control colors still require contrast checks; Bulma is not WCAG certification.
'''


def component_instruction(framework):
    if framework == 'bootstrap':
        return BOOTSTRAP_PATTERNS + '\nRequired behavior bundle when applicable: ' + BOOTSTRAP_BUNDLE
    if framework == 'bulma':
        return BULMA_PATTERNS
    if framework == 'pico':
        return 'Pico styles semantic HTML, .container, .grid, article cards and native details/summary; it supplies no JavaScript behaviors. Prefer native interactions.'
    raise ValueError('Unsupported regeneration design base')
