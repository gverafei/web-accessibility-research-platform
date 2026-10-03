# Browser extension

The extension lets a researcher initiate A11yResearch remediation from an active web tab. The backend still performs the acquisition, measurement and repair, so a research experiment is not tied to keeping the side panel open.

## Install from source

1. Start A11yResearch at `http://localhost`.
2. Open `chrome://extensions` (or the equivalent in a compatible Chromium browser).
3. Enable Developer mode.
4. Choose **Load unpacked** and select the repository's `browser_extension` directory.
5. Open a public HTTP(S) page and click the A11yResearch extension icon.

The source uses the Chromium extension APIs, including its side-panel API. Chrome and Edge are the documented local prototype targets. Other Chromium browsers may support the necessary APIs but are not automatically certified by A11yResearch. Firefox and Safari are not supported by this unchanged build.

The manifest uses extension format version 3: a browser packaging/API contract, not a A11yResearch experiment version. Its background worker can be inactive between events without indicating an error.

## Controls

The panel shows the active URL, model/reasoning slider, five intervention policies and an optional ACT retrieval switch. The header settings button opens the language and appearance controls, identified by globe and theme icons. The model catalogue, colors and default selection come from A11yResearch Configuration, not a duplicated hard-coded extension list.

An explicit model snapshot and research targets are frozen at request submission, before a new acquisition can complete. A later catalogue/target edit cannot change that pending experiment.

## What happens after submission

**Use stored results** is enabled by default. Matching uses the normalized URL and the two sliders: the actual model/reasoning choice and intervention level. RAG-ACT, targets and catalogue presentation changes do not prevent recovery. Retained results from normal backend runs are also available, even if a newer acquisition exists. An equivalent request still in progress is followed rather than duplicated. Recovery makes no generation or evaluation call and keeps the original source, timestamps, targets and recorded RAG setting; the completion panel describes that saved run. Failed runs, missing candidates and zero-shot runs are not reused as iterative repairs. Both interfaces start at **Minimal patches**.

If no acquisition exists, A11yResearch queues a one-page acquisition before remediation. To capture the current remote page again and repeat remediation, disable **Use stored results** before submitting. This may incur model charges. Existing sources, results and their original timestamps remain unchanged.

On completion, the panel compares original and retained-final Axe issue instances and Lighthouse scores alongside the frozen targets. A dash denotes an unavailable measurement, not a zero. **View full report** opens the run's iteration trace and detailed evidence. The final scores belong to the retained candidate, which may be an earlier iteration than the last attempt. These measurements remain available when the panel is reopened.

For regeneration, the extension selects Bootstrap. Alternative design bases and the independent zero-shot baseline are available in the full web module.

## Capture scope

The extension sends the **URL**, not the authenticated session, cookies or exact DOM in the active tab. Content requiring your login may therefore differ from what the backend can acquire. Dynamic content is handled by the subsequent controlled browser acquisition.

A retained candidate replaces the HTML directly in the original tab, preserving the tab's HTTP(S) address and origin. The extension fetches the stored candidate from the local platform; it does not add an iframe, use a blob URL or navigate the tab to localhost. The saved candidate and measurements are unchanged.

The original URL remains the experiment and cache identity. **Return to original website** reloads the remote page. Browser-based evaluators such as the [WAVE extension](https://wave.webaim.org/extension/) can inspect the document displayed in the tab, subject to their permissions. A remote evaluation service given that URL sees the remote website, not the candidate injected into your browser.

This is a temporary inspection view, not a change to the remote website or a security sandbox. Replacing the HTML does not create a fresh JavaScript environment. Existing timers, asynchronous callbacks or widget state can interfere with the new document and duplicate dynamic content. Keeping the source origin avoids the origin change introduced by local-page inspection, but does not guarantee that every resource or interaction works. Reloading the original website restores its own document and execution context. Verify the candidate's accepted/warning status and relevant interactions before using it in a user study.

## Update and diagnose

After changing extension files, use its reload button in the browser extension manager and reopen the side panel. Check that the A11yResearch service is reachable and that the chosen model is configured. An idle extension service worker is normal; an unavailable backend or provider is not.

The shipped prototype uses localhost and broad HTTP(S) permissions to operate on an active page. Review permissions and [security boundaries](../technical/security.md) before deploying in a managed research environment. The [HTTP interface](../technical/api.md) documents the same backend request contract.
