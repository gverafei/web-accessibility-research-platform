# Configuration

Open **Configuration** from the application menu. Its two tabs have independent save operations: **General** saves application settings; **Model catalogue** saves the researcher-managed model choices. Switching tabs preserves the current form in the page, but is not a save.

Both save buttons show the same loading spinner while their request is pending.
Success or failure appears in the same dismissible notice above the page content.
Saving the catalogue keeps its tab open; a failed save retains the unsaved edits.

The selected tab uses `#general` or `#models`, which are navigation state rather
than panel anchors, so saving or reloading does not jump down to the tab content.
Older bookmarked panel links still open the appropriate tab.

## General settings

The icon in the top bar cycles through **Dark → Light → Follow operating
system → Dark** with each click. The moon, sun and monitor show the selected
mode; its tooltip names the current and next mode. Keyboard activation works
the same way. The choice is saved for this browser session without reloading
the page or discarding unsaved form fields. System mode follows OS changes.

Light uses soft colored fills and defined borders; dark uses the same component
roles with higher-contrast text and outlines. The web interface and extension
share this treatment. Remediation sliders keep their distinct model and
intervention colors in both modes.

The sidebar and top bar use a slightly darker surface than the content area.
Descriptive metric cards use neutral colors; green, amber and red remain for
meaningful states and changes, rather than implying that every displayed value
is a successful outcome.
Evaluation and remediation history tables share the same row-hover treatment
in both themes.

Use the primary **Save configuration** button at the top right after changing general settings. These include evaluator options, acquisition timing, provider credentials, local Ollama configuration and remediation research targets.

### Research targets

The bundled defaults are Lighthouse ≥94 and Axe ≤3. They are engineering targets for a remediation experiment, not values inferred from a statistical sample or thresholds that establish accessibility conformance. Choose values appropriate to your study and describe that choice in its protocol.

Changing the intervention level does not change these targets. New submissions freeze the chosen values; a later configuration edit does not rewrite the targets in existing remediation runs or pending extension requests.

**Resource limits per run**, in the same panel, lets you set maximum iterations
(1–10, initially 3), a cost limit in USD (0.01–100, initially US$0.25) and a time
limit in seconds (30–7,200, initially 360 seconds). Cost/time values are shared
across all five intervention levels; moving a slider does not change them.
Single-call modes always use one iteration.
These are limits for each new run, not a shared allowance for a collection.

Cost/time thresholds stop continuation between operations; an operation already
in progress can finish beyond them. They are not guaranteed provider-bill or
wall-clock caps. Web submissions and extension requests freeze the effective
limits. Stored-result reuse returns the existing run and its original settings;
changing limits does not invalidate that result. Disable reuse only when you
intend to execute a fresh run, which can incur new charges.

### Evaluator controls

Select the default Axe standard for new evaluations. The four report-display switches
apply to existing reports when you save Configuration and reopen or reload the report:
Best Practices adds a separate **Best-practice issues** column immediately after
**Axe issues**; Failed rules and Needs review show their URL-matrix columns; densities
show two normalized matrix columns and their overview metrics. These controls do not
repeat the scan or change the stored acquisition profile. An unavailable legacy count
is displayed as a dash, not zero.

Main Axe scores, charts, comparisons and remediation targets always exclude Best
Practices. WCAG counts, Best Practices and the combined count are preserved separately.
Set dynamic-page timing and scrolling consistently across experiments you intend to compare.

Disabling lazy-content activation disables its pointer/scroll controls, not the
page-load and DOM-stability limits. The stored scroll values are retained for
reuse when the option is enabled again. **Internal dataset**, immediately above
Regional settings, uses `https://example.org/` when its URL list is empty.

WAVE is optional, requires its own key and is used for separate evaluations. It is not a paid criterion in the remediation loop.

### Local LLM (Ollama)

Ollama is not included in the six-service Compose deployment. Run it on a reachable host, enter the base address, use **Refresh installed models** to verify the connection, and select a model.

The refresh control uses the address currently typed in the form. It discovers
installed models through Ollama's native API and inspects capabilities without
generating content or requiring a save first. If capability inspection fails
for a model, it remains visible as unverified; refresh before selecting it.

On Docker Desktop, a host service commonly uses `http://host.docker.internal:11434`. This depends on how Ollama is bound and your firewall; `localhost` inside the worker refers to the worker container, not your computer. Confirm reachability before submitting a local experiment.

The local choice appears when both its address and model are configured. If Ollama is unavailable, A11yResearch reports the failure rather than selecting a different model or cloud provider.

### RAG-ACT is a separate workspace

Use **RAG-ACT** near the bottom of the main sidebar to initialize/update knowledge
or inspect saved examples. These operations are no longer inside Configuration
and are independent of saving settings or enabling retrieval in a remediation.
See [Adaptive RAG-ACT](rag.md).

## Model catalogue

Read [Models and reasoning](models.md) for discovery, manual identifiers, capabilities and ordering. Its **Save model catalogue** button commits only that catalogue. Existing runs retain their saved snapshots and digests.

**Add model from OpenRouter** opens the provider picker and scrolls it into view.
Its loading or error message is shown inside the picker; discovery is read-only,
and selecting a model changes the draft until you save the catalogue.

## Settings and reproducibility

The effective configuration combines environment defaults with persisted `app_settings` values. A saved value takes precedence over its environment default. Changing `.env` is therefore not always sufficient to change a setting already saved through the UI.

Keep secrets out of protocols, screenshots, exports and support tickets. Record the meaningful non-secret controls, source revision and actual run configuration instead. See the [settings reference](../technical/settings.md) for defaults, storage and validation.

!!! warning "Maintenance actions"
    Clearing evaluations or deleting runs removes research records and can remove associated artifacts. An export or backup preserves the relevant evidence before cleanup. Connection diagnostics are available separately from these data-removal actions.
