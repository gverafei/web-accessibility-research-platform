# Models and reasoning

WARP keeps the model catalogue editable so a researcher can adopt a new model without changing the application or extension source. Model discovery reads provider metadata; it does not generate content or replace models in existing experiments.

## Fresh-install defaults

The bundled catalogue lives in `web/app/remediation_model_choices.py`, in `default_catalog()`. A saved catalogue takes precedence; an application update does not overwrite a researcher's choices.

| Choice | Explicit model identifier | Reasoning setting |
| --- | --- | --- |
| Llama 4 Maverick | `meta-llama/llama-4-maverick` | Unspecified |
| Qwen3 Coder Plus | `qwen/qwen3-coder-plus` | Unspecified |
| GPT-6 Luna — default | `openai/gpt-6-luna` | Light (`low`) |
| Gemini 3.8 Flash | `google/gemini-3.8-flash` | High |
| GPT-6 Luna | `openai/gpt-6-luna` | High |
| GPT-6 Sol | `openai/gpt-6-sol` | Light (`low`) |
| GPT-6 Astra | `openai/gpt-6-astra` | Light (`low`) |
| Claude Opus 5.5 | `anthropic/claude-opus-5.5` | Light (`low`) |

These are the identifiers configured in this source revision. Provider availability and support can change; check discovery and a bounded pilot before using a choice. The list is not a benchmark or current price catalogue.

## Add a model from OpenRouter

1. Open **Configuration → Model catalogue**.
2. Use the OpenRouter discovery control to load the live metadata list.
3. Search by its provider/name and add the desired model.
4. Review the display name, color, reasoning and capability fields.
5. Reorder or disable choices and choose one enabled default.
6. Click **Save model catalogue**.

The web and extension sliders use the enabled saved choices in their configured order. Provider icons follow the provider family; an unknown provider is still a usable catalogue entry with a generic identity rather than a reason to substitute a known model.

## Future models and manual identifiers

If a newly announced model is not yet discoverable, you can enter its **exact provider-qualified identifier**. For example, a hypothetical identifier `example-provider/new-research-model` is syntactically valid, but WARP does not guarantee that it exists. Confirm the identifier with OpenRouter before a paid run.

Each choice has its own unique ID. That permits the same model with different reasoning settings, as in Luna Light and High. The catalogue accepts 1–32 choices, at least one enabled choice, and at most one enabled default. Router aliases and local Ollama aliases are not accepted as cloud catalogue entries.

## Capabilities

Catalogue metadata describes image input, temperature support, reasoning support, context length and output limits when available. Discovery stores its source/time. These fields affect request preparation, so do not enable unsupported capabilities merely to make a control appear.

“Light” maps to provider effort `low`. Reasoning settings do not select a separate model ID. Higher effort can change token consumption and duration even without a different listed per-token price. WARP records actual usage/charges instead of presenting a price estimate as a stable property of a slider position.

## Frozen selection and failure

At submission, `frozen_model_configuration()` saves the choice and its SHA-256 digest. Later catalogue edits cannot turn an existing Luna experiment into a different model. WARP does not automatically replace a failed selection, switch provider or fall back from Ollama to the cloud.

If a model is retired, update the catalogue for **new** runs and report the change. Do not rewrite an old run to make it appear to have used its replacement.

## Local models

Configure an installed Ollama model under General settings. That creates a separate explicit local choice; it does not come from OpenRouter discovery. Context rejection is reported rather than silently truncating the complete source. See [Configuration](configuration.md) and [Troubleshooting](../reference/troubleshooting.md).
