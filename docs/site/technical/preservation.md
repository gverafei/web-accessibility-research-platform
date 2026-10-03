# Preservation measurements

Accessibility gains can accompany undesirable content, structure or interaction changes. A11yResearch records several preservation measures so a researcher can inspect that trade-off. None is a complete semantic or usability proof.

## Indicators and their roles

Source means the stored original; candidate means an evaluated repair. Counts
of tags, model tokens and pixels describe different things and must not be
treated as interchangeable.

| Indicator | What it measures | How it is calculated | What it is used for |
| --- | --- | --- | --- |
| Axe WCAG issues | Automated violation instances | Counts affected elements for each failed WCAG rule; excludes Best Practices. | Accessibility targets and acceptance. |
| Lighthouse score | Accessibility audits | Uses Lighthouse's weighted accessibility score, from 0 to 100. | Accessibility targets and acceptance. |
| WAVE AIM (optional) | Independent WAVE accessibility summary | Reads the AIM score returned by the WAVE API; the platform does not calculate it from Axe or Lighthouse. | Separate evaluation/comparison evidence when available; not a target in the current five-level remediation workflow. |
| Text retention | Original words preserved | Divides retained original word occurrences by the original word count, as a percentage. | Preservation and candidate ranking. |
| Link retention | Original destinations preserved | Calculates the percentage of unique original link destinations present in the candidate. | Preservation and candidate ranking. |
| Image retention | Original images preserved | Calculates the percentage of unique original image URLs present in the candidate. | Preservation and candidate ranking. |
| Media/banner retention | Captured media preserved | Calculates the percentage of original image, video-poster and inline-background URLs found in the evaluated candidate. | Preservation and candidate ranking. |
| Overall content retention | Combined preservation summary | Averages available text, link, image and media percentages with equal weight. | Report summary, not acceptance or ranking. |
| Matching structural units | HTML structure shared by both pages | Counts each opening and closing tag as one unit, then matches groups in order. Attributes such as role and alt affect matching, not the count. | Input to DOM divergence. |
| DOM divergence | Structural units that do not match | Subtracts matches from each page's count and reports the unmatched percentage across both pages. | Describing structural change, not content loss or acceptance. |
| RGB visual similarity | Screenshot colour resemblance | Crops and resizes both captures identically; averages red, green and blue differences between corresponding pixels. Smaller differences give higher similarity. | Candidate tie-breaking at levels 1–3, not functionality testing. |
| Axe issue reduction | Change relative to the original | Reports the decrease as a percentage of original issues; an increase gives a negative value. | Showing improvement or regression. |
| Lighthouse gap recovered | Recovery of points missing from 100 | Reports score improvement as a percentage of the original shortfall from 100. | Showing progress toward a perfect score. |
| Distance to targets (internal) | Remaining accessibility shortfall | Adds issues above the Axe limit and points below the Lighthouse target. With limits 3 and 94, scores 8 and 90 leave 5 excess issues plus 4 missing points: distance 9. | Candidate ranking and retention of the best evaluated result. |
| Time, cost and model tokens | Execution resource use | Records durations, actual provider charges and input/output tokens from execution and model responses. | Accounting and execution limits. |

Optional WAVE AIM is reported separately when enabled. Missing measurements
are not zero scores. See [evaluation metrics](evaluation.md) for counting
profiles and [agent runtime](agent-runtime.md) for ranking and acceptance.

## Structural comparison

`dom_distance()` in `web/app/remediation_jobs.py` uses Python `SequenceMatcher`
with `autojunk=False`. Each opening or closing tag is one unit. Role, type,
ARIA naming/description/live attributes, alt, for and name are attached to
those units for matching; they do not add units. These sequence lengths are
the report's HTML structure counts, not a separate preservation score or the
evaluator's number of DOM element nodes.

For example, sequences of 1,816 and 1,604 units with 1,398 matches leave 418
and 206 unmatched units. Together, 624 of 3,420 units do not match: 18.25%
DOM divergence. The lengths alone cannot determine it. This compares ordered
sequences, not DOM tree-edit operations. `dom_change_summary()` separately
describes added/removed tags and accessibility attributes.

## Content and screenshot details

Word matching uses normalized word occurrences and omits script/style/noscript/
SVG data; it is not a CSS-visibility or meaning check. Unique resource URLs
avoid counting responsive duplicates twice. Empty original resource sets yield
100% retention. A retained URL does not prove successful loading, and retained
words do not prove usable navigation or preserved meaning. Inspect forms,
navigation, media and actual controls as well as percentages.

RGB comparison crops both images to their common upper region, at most 1,200
pixels high, converts to RGB and resizes to 128×96. It compares corresponding
pixels in these reduced images, not every full-resolution page pixel. The
mean absolute channel difference is scaled against the maximum difference of
255 to obtain a similarity percentage. Missing or unreadable screenshots have
no similarity value. It is not a trained perceptual metric or an interaction
test.

Dynamic resources and native-form contracts can contribute additional warnings
and ranking/refinement evidence. Inspect the actual iteration's strategy fields
instead of applying a universal content threshold to every historical run.

## Captured-widget replay

Rendered HTML can contain widget wrappers created by JavaScript, but it does not
retain the plugin's in-memory instance. Re-executing a content loader against
that populated HTML can duplicate slides or overwrite captured media.

`prepare_frozen_widget_replay()` in `web/app/remediation_content_contract.py`
uses bounded adapters for repair levels 1–3. The Slick adapter lives in
`web/app/frozen_carousel_replay.py` and its accompanying JavaScript file. It
recognizes the library and generated list/track/slide structure, retains the
candidate's original slide content and arrow markup, and reinitializes the same
library. A scoped jQuery guard prevents content loaders from rebuilding those
frozen regions; other page regions remain editable. Responsive plugin rebuilds
and navigation retain their own scoped permission.

Ambiguous structures and clones with distinct content are left unchanged.
Adapter versions, runtime digests and observed replay warnings appear in iteration
evidence. This is not a sandbox for arbitrary native DOM mutations, a guarantee
for every carousel library, or an interaction-equivalence measurement. Inspect
the candidate's actual controls and content as well as its scores.

## Interpretation

Use measured target changes, content/destination retention, DOM changes, screenshots and manual inspection together. A small divergence can conceal a broken action; a regenerated layout can differ substantially while retaining the relevant information. Keep the intervention policy and recorded warnings visible when making comparisons.
