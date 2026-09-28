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

These defaults are editable. OpenRouter discovery provides current availability and capability metadata for configuring a choice.

## Add a model from OpenRouter

1. Open **Configuration → Model catalogue**.
2. Use the OpenRouter discovery control to load the live metadata list.
3. Search by its provider/name and add the desired model.
4. Review the display name, color, reasoning and capability fields.
5. Reorder or disable choices and choose one enabled default.
6. Click **Save model catalogue**.

The web and extension sliders display enabled choices in the saved order. Provider icons follow the provider family, with a generic icon for providers outside the bundled icon set.

## Future models and manual identifiers

Models can also be added manually using their **exact provider-qualified identifier** from OpenRouter. Identifiers follow the form `provider/model-name`; discovery is a convenient way to obtain the ID and supported capabilities together.

Each choice has its own unique ID. That permits the same model with different reasoning settings, as in Luna Light and High. The catalogue accepts 1–32 choices, at least one enabled choice, and at most one enabled default. Router aliases and local Ollama aliases are not accepted as cloud catalogue entries.

## Capabilities

Catalogue metadata describes image input, temperature support, reasoning support, context length and output limits when available. Discovery records its source and time. WARP uses these fields to prepare requests compatible with the selected model.

“Light” maps to provider effort `low`. Reasoning settings do not select a separate model ID. Higher effort can change token consumption and duration even without a different listed per-token price. WARP records actual usage/charges instead of presenting a price estimate as a stable property of a slider position.

## Frozen selection and failure

At submission, `frozen_model_configuration()` in `web/app/remediation_model_choices.py` saves the choice and its SHA-256 digest. The run continues with that configuration after later catalogue edits. Provider failures appear in its report; model changes are selected when creating a new run.

Catalogue updates apply to new runs. Existing runs retain their original model and reasoning settings, including choices subsequently retired by the provider.

## Local models

Configure an installed Ollama model under General settings. Local choices are managed separately from OpenRouter discovery. A context-capacity error appears in the run report with the selected local model's details. See [Configuration](configuration.md) and [Troubleshooting](../reference/troubleshooting.md).
