# Configuration

Open **Configuration** from the application menu. Its two tabs have independent save operations: **General** saves application settings; **Model catalogue** saves the researcher-managed model choices. Switching tabs preserves the current form in the page, but is not a save.

## General settings

Use the primary **Save configuration** button at the top right after changing general settings. These include evaluator options, acquisition timing, provider credentials, local Ollama configuration and remediation research targets.

### Research targets

The bundled defaults are Lighthouse ≥94 and Axe ≤3. They are engineering targets for a remediation experiment, not values inferred from a statistical sample or thresholds that establish accessibility conformance. Choose values appropriate to your study and describe that choice in its protocol.

Changing the intervention level does not change these targets. New submissions freeze the chosen values; a later configuration edit does not rewrite the targets in existing remediation runs or pending extension requests.

### Evaluator controls

Select the Axe standard and whether Best Practices should be shown. WARP retains the relevant tool evidence and makes display choices separate from the source acquisition. Set dynamic-page timing and scrolling consistently across experiments you intend to compare.

WAVE is optional, requires its own key and is used for separate evaluations. It is not a paid criterion in the remediation loop.

### Local LLM (Ollama)

Ollama is not included in the six-service Compose deployment. Run it on a reachable host, enter the base address, refresh the installed model list, select a model, and use the test control within this panel.

On Docker Desktop, a host service commonly uses `http://host.docker.internal:11434`. This depends on how Ollama is bound and your firewall; `localhost` inside the worker refers to the worker container, not your computer. Confirm reachability before submitting a local experiment.

The local choice appears when both its address and model are configured. If Ollama is unavailable, WARP reports the failure rather than selecting a different model or cloud provider.

## Model catalogue

Read [Models and reasoning](models.md) for discovery, manual identifiers, capabilities and ordering. Its **Save model catalogue** button commits only that catalogue. Existing runs retain their saved snapshots and digests.

## Settings and reproducibility

The effective configuration combines environment defaults with persisted `app_settings` values. A saved value takes precedence over its environment default. Changing `.env` is therefore not always sufficient to change a setting already saved through the UI.

Keep secrets out of protocols, screenshots, exports and support tickets. Record the meaningful non-secret controls, source revision and actual run configuration instead. See the [settings reference](../technical/settings.md) for defaults, storage and validation.

!!! warning "Maintenance actions"
    Clearing evaluations or deleting runs removes research records and can remove associated artifacts. An export or backup preserves the relevant evidence before cleanup. Connection diagnostics are available separately from these data-removal actions.
