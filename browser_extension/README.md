# WARP Accessible Page extension

Local Chrome/Edge Manifest V3 prototype. It uses the active tab URL, reuses a frozen WARP acquisition when available, or queues a one-page acquisition before remediation.

1. Open `chrome://extensions` or `edge://extensions`.
2. Enable Developer mode.
3. Choose **Load unpacked** and select this `browser_extension` directory.
4. Open an HTTP(S) page and click the WARP extension icon.

The prototype expects WARP at `http://localhost` and keeps acquisitions, remediation runs, candidates, metrics, and evidence in the existing application database and artifact directories.

The model slider reads the researcher's saved catalogue from WARP Configuration,
including order, colors, enabled choices and explicit reasoning. New models can
be selected from OpenRouter's live metadata list without editing this extension.
Each request freezes the chosen configuration before acquisition; a later
catalogue edit cannot change it. An explicit model failure never selects a
different model or falls back from Ollama to a cloud provider.

The intervention slider shares the platform's five policies: minimal patches,
localized repair, coordinated repair, HTML regeneration and Markdown
regeneration. Axe/Lighthouse acceptance targets remain constant across levels.
The extension's regeneration design base is Bootstrap; other design bases and
the independent zero-shot baseline remain available in the full web module.

This is URL-based acquisition, not an export of the current tab DOM, login
session or cookies. Applying a retained candidate replaces the current tab
document temporarily; it does not modify the remote website. Reload the
unpacked extension after updating these files.
