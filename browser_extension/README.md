# A11yResearch Accessible Page extension

Local Chrome/Edge Manifest V3 prototype. It uses the active tab URL, reuses a frozen A11yResearch acquisition when available, or queues a one-page acquisition before remediation.

1. Open `chrome://extensions` or `edge://extensions`.
2. Enable Developer mode.
3. Choose **Load unpacked** and select this `browser_extension` directory.
4. Open an HTTP(S) page and click the A11yResearch extension icon.

The prototype expects A11yResearch at `http://localhost` and keeps acquisitions, remediation runs, candidates, metrics, and evidence in the existing application database and artifact directories.

The model slider reads the researcher's saved catalogue from A11yResearch Configuration,
including order, colors, enabled choices and explicit reasoning. New models can
be selected from OpenRouter's live metadata list without editing this extension.
Each request freezes the chosen configuration before acquisition; a later
catalogue edit cannot change it. An explicit model failure never selects a
different model or falls back from Ollama to a cloud provider.

The **Use stored results** switch is on by default. A retained remediation with
the same normalized URL and two sliders (model/reasoning and intervention) is
recovered without new model calls, including results created from the backend.
RAG, targets and catalogue presentation do not invalidate it. Completion keeps
the saved run's real RAG setting and targets, not the current controls;
an equivalent active request is followed. Disable the switch to repeat both
acquisition and remediation, with possible model charges. Completion shows
original and retained-final Axe/Lighthouse measurements, frozen targets and a
link to the full report. Missing measurements are shown as a dash.

The intervention slider shares the platform's five policies: minimal patches,
localized repair, coordinated repair, HTML regeneration and Markdown
regeneration. Axe/Lighthouse acceptance targets remain constant across levels.
The extension's regeneration design base is Bootstrap; other design bases and
the independent zero-shot baseline remain available in the full web module.

This is URL-based acquisition, not an export of the current tab DOM, login
session or cookies. Applying a retained candidate replaces the HTML directly in
the original tab, keeping its HTTP(S) address and origin. It does not add an
iframe, use a blob URL or navigate to localhost. The stored candidate is fetched
from the local platform and remains unchanged. This delivery replaces the DOM,
not the complete JavaScript environment: existing asynchronous callbacks or
widget state can interfere with the candidate and may duplicate dynamic content.
**Return to original website** explicitly reloads the remote page when the URL
has not changed, or navigates back to the original URL otherwise. This is a temporary
inspection view, not a remote modification or security sandbox; scripts that
depend on runtime state or browser security policies may behave differently.
Reloading the original website restores its own document and JavaScript context.
Reload the unpacked extension after updating these files.

General components share the web application's light/dark skin. Remediation
sliders retain their own styling. After editing `web/app/static/css/theme.css`,
run `python web/tools/sync_theme_assets.py` to refresh the packaged local copy;
the extension does not fetch this stylesheet from localhost at runtime.
