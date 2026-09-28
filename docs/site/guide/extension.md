# Browser extension

The extension lets a researcher initiate WARP remediation from an active web tab. The backend still performs the acquisition, measurement and repair, so a research experiment is not tied to keeping the side panel open.

## Install from source

1. Start WARP at `http://localhost`.
2. Open `chrome://extensions` (or the equivalent in a compatible Chromium browser).
3. Enable Developer mode.
4. Choose **Load unpacked** and select the repository's `browser_extension` directory.
5. Open a public HTTP(S) page and click the WARP extension icon.

The source uses the Chromium extension APIs, including its side-panel API. Chrome and Edge are the documented local prototype targets. Other Chromium browsers may support the necessary APIs but are not automatically certified by WARP. Firefox and Safari are not supported by this unchanged build.

The manifest uses extension format version 3: a browser packaging/API contract, not a WARP experiment version. Its background worker can be inactive between events without indicating an error.

## Controls

The panel shows the active URL, model/reasoning slider, five intervention policies and optional ACT retrieval. The model catalogue, colors and default selection come from WARP Configuration, not a duplicated hard-coded extension list.

An explicit model snapshot and research targets are frozen at request submission, before a new acquisition can complete. A later catalogue/target edit cannot change that pending experiment.

## What happens after submission

WARP reuses an available completed frozen acquisition for the normalized URL or queues a one-page acquisition. It then creates a new remediation run with the submitted controls. The panel reads persistent request/run progress.

For regeneration, the extension selects Bootstrap. Alternative design bases and the independent zero-shot baseline are available in the full web module.

## Capture scope

The extension sends the **URL**, not the authenticated session, cookies or exact DOM in the active tab. Content requiring your login may therefore differ from what the backend can acquire. Dynamic content is handled by the subsequent controlled browser acquisition.

A retained candidate can replace the local tab document for inspection. This is a temporary local view, not a change to the remote website. Reload the page to restore its original document. Verify the candidate's accepted/warning status before using it in a user study.

## Update and diagnose

After changing extension files, use its reload button in the browser extension manager and reopen the side panel. Check that the WARP service is reachable and that the chosen model is configured. An idle extension service worker is normal; an unavailable backend or provider is not.

The shipped prototype uses localhost and broad HTTP(S) permissions to operate on an active page. Review permissions and [security boundaries](../technical/security.md) before deploying in a managed research environment. The [HTTP interface](../technical/api.md) documents the same backend request contract.
