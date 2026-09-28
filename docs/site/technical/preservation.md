# Preservation measurements

Accessibility gains can accompany undesirable content, structure or interaction changes. WARP records several preservation measures so a researcher can inspect that trade-off. None is a complete semantic or usability proof.

## DOM divergence

`dom_distance()` parses start/end tag tokens and selected accessibility-relevant attributes: role, type, ARIA naming/description/live attributes, alt, for and name. It applies Python `SequenceMatcher` with `autojunk=False` to the two token sequences.

Let `M` be the matched token count and `T_o`, `T_c` the sequence lengths:

```text
Similarity = 2M / (T_o + T_c)
DOM divergence (%) = 100 × (1 − similarity)
```

An unchanged token sequence produces zero divergence. This is not a DOM tree-edit distance: it excludes many attributes and text content. The returned sequence lengths include end-tag tokens and must not be mislabeled as the evaluator's DOM-node counts.

`dom_change_summary()` separately counts added/removed element tags and added accessibility attributes. The current run evidence records DOM divergence without enforcing it as an automatic rejection threshold.

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

## Interpretation

Use measured target changes, content/destination retention, DOM changes, screenshots and manual inspection together. A small divergence can conceal a broken action; a regenerated layout can differ substantially while retaining the relevant information. Keep the intervention policy and recorded warnings visible when making comparisons.
