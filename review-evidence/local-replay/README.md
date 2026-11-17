# Matched local replay of 125 remediation pairs

These measurements accompany the Minimal patches example. Each row links one stored original to its retained candidate by pair ID, run ID and SHA-256 hashes. The four submitted scores and four matched scores in [paired_measurements.csv](paired_measurements.csv) let readers compare both protocols for each page.

The submitted comparison measured the original on the live site and its candidate on the local server. Historical candidate reports show that three Lighthouse audits and one Axe audit navigated away from the local document across three pages. The evaluator now blocks replacement of the locally served main document while allowing referenced resources to load. The matched comparison evaluated both stored states locally with the same resource resolution and tool settings, including the same desktop Lighthouse profile. All 125 candidates were reused. [Measurement configuration](configuration.json)

A pair counts once if the candidate has more WCAG Axe issue instances or a lower Lighthouse accessibility score than its own original. Equal scores do not qualify. The columns ending in `_left_local_origin` identify the historical candidate audits whose document left the local origin.

| Submitted comparison | Matched comparison | Pairs |
| --- | --- | ---: |
| Regression | Regression | 6 |
| Regression | No regression | 16 |
| No regression | Regression | 6 |
| No regression | No regression | 97 |

The submitted count was 22 and the matched count was 12. Among the latter, nine candidates worsened on Axe and four on Lighthouse, with one counted by both. Of the three pages with a documented departure from the local origin, only one was originally classified as a regression. The count difference reflects the combined change in measurement conditions. This comparison does not isolate the effect of the navigation fix or test an alternative repair strategy.

## Reproduce the counts and estimates

From this directory, run the following with Python and NumPy (analysis versions 3.12.14 and 2.3.5). The script calculates both regression flags from the scores, checks them against the CSV, and prints the transition counts, matched summaries and within-stratum bootstrap intervals.

```sh
python analyze_measurements.py paired_measurements.csv
```
