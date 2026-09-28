# Dynamic-page acquisition

Modern pages often reveal content only after script execution, delayed network requests or scrolling. WARP uses a bounded acquisition policy to expose more of that content before retaining HTML and screenshots.

## Acquisition sequence

The browser workflow combines navigation/load observation, bounded network-idle attempts, bidirectional lazy-load scrolling, a DOM-stability observation and a final settling period. It then retains the rendered evidence available from that visit.

These controls make a visit more repeatable; they are not a general-purpose user journey that automatically signs in, solves challenges or clicks every interactive state.

| General setting | Default | Purpose |
| --- | ---: | --- |
| Page load timeout | 60,000 ms | Navigation budget |
| Network idle timeout | 15,000 ms | Bounded network-idle observation |
| Final settle delay | 2,000 ms | Wait before final capture |
| DOM stability window | 1,500 ms | Observe stabilization |
| DOM stability timeout | 10,000 ms | Bound the stability wait |
| Lazy-load scrolling | Enabled | Reveal content outside the initial viewport |
| Scroll step | 700 px | Scroll increment |
| Scroll delay | 400 ms | Allow loading between steps |
| Maximum scroll steps | 30 | Bound traversal |

These are the defaults in `settings.py`; environment values, including those in `.env.example`, and saved configuration can override them. Inspect the stored acquisition metadata for what actually happened in a particular run. Browser-level errors or early exits can prevent a complete sequence.

## Tune through a pilot

1. Choose examples representing long pages, lazy images and script-heavy layouts.
2. Acquire them and compare the screenshots with an ordinary browser visit.
3. Inspect captured HTML and load metadata for missing regions or unfinished loading.
4. Change the relevant timing/scroll control only if there is a defensible reason.
5. Record the selected policy and hold it fixed during the main study.

Increasing every timeout can substantially increase cost and duration without revealing content hidden behind authentication or a required interaction. Treat a blank/error/challenge page as an acquisition issue, not an automatically accessible page.

## Tool independence

Axe and Lighthouse can observe different browser states. WAVE requests public URLs independently and cannot analyze the internal dataset-server URL like a local browser can. Their outputs should be interpreted with their tool/version and capture context, not as interchangeable measurements of a guaranteed identical DOM.

The extension uses this same backend acquisition behavior. It submits the page URL, not the current tab's live state. See [Browser extension](extension.md) and [Evaluation pipeline](../technical/evaluation.md).
