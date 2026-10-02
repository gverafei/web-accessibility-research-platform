# Preservation measurements

Accessibility gains can accompany undesirable content, structure or interaction changes. A11yResearch records several preservation measures so a researcher can inspect that trade-off. None is a complete semantic or usability proof.

## DOM divergence

`dom_distance()` in `web/app/remediation_jobs.py` parses start/end tag tokens and selected accessibility-relevant attributes: role, type, ARIA naming/description/live attributes, alt, for and name. It applies Python `SequenceMatcher` with `autojunk=False` to the two token sequences.

Let `M` be the matched token count and `T_o`, `T_c` the sequence lengths:

```text
Similarity = 2M / (T_o + T_c)
DOM divergence (%) = 100 × (1 − similarity)
```

An unchanged token sequence produces zero divergence. The measure compares token sequences rather than DOM tree-edit operations. Sequence lengths include end tags and differ from the evaluator's count of DOM element nodes.

`dom_change_summary()`, also in `web/app/remediation_jobs.py`, counts added/removed element tags and added accessibility attributes. DOM divergence appears in iteration evidence for inspection rather than as an automatic rejection threshold.

## Content retention

Text retention uses the multiset intersection of normalized visible-text tokens while omitting script/style/noscript/SVG data. Destination and image retention use unique original URLs; responsive duplicates count once.

```text
Text retention = 100 × Σ min(original_word_count, candidate_word_count)
                         / original_word_total
Link retention = 100 × |original_destinations ∩ candidate_destinations|
                         / |original_destinations|
Image retention = 100 × |original_image_URLs ∩ candidate_image_URLs|
                          / |original_image_URLs|
```

Empty original destination/image sets yield 100% for those measures. A retained word/URL does not establish that it remains usable or occurs in the right context. Review forms, navigation and meaningful visual content in addition to the percentages.

Dynamic resources and regeneration/native-form contracts can contribute additional warnings and ranking/refinement evidence. Inspect the actual iteration's strategy fields instead of applying a universal content threshold to every historical run.

## Screenshot similarity

The implementation crops both images to their common top region (up to 1,200 pixels), converts to RGB, resizes to 128×96 and computes the mean absolute channel difference:

```text
Visual similarity (%) = max(0, 100 × (1 − mean_absolute_difference / 255))
```

Unavailable/unreadable screenshots yield no similarity. This coarse display comparison is not a trained perceptual metric, an interaction test or a measure of full-page semantic equivalence. It can be a tie-break for preservation-oriented repairs, not an accessibility acceptance gate.

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
