"""Researcher-managed choices; each run freezes its model configuration."""
import hashlib
import json
import re
from datetime import datetime, timezone
import requests

CATALOG_SETTING = 'remediation_model_catalog_json'
TIERS = ('low', 'medium', 'high', 'xhigh', 'max')
EFFORTS = (None, 'none', 'minimal', 'low', 'medium', 'high', 'xhigh')
PROVIDER_DEFAULT_MODELS = {'openai': 'openai/gpt-6-luna', 'google': 'google/gemini-3.8-flash', 'meta-llama': 'meta-llama/llama-4-maverick', 'qwen': 'qwen/qwen3-coder-plus', 'anthropic': 'anthropic/claude-opus-5.5'}


def default_catalog():
    definitions = (
        ('meta-llama/llama-4-maverick', 'Llama 4 Maverick', 'low', None, '#b76a12', True, True),
        ('qwen/qwen3-coder-plus', 'Qwen3 Coder Plus', 'medium', None, '#2686c9', False, True),
        ('openai/gpt-6-luna', 'GPT-6 Luna', 'high', 'low', '#2f9e66', True, False),
        ('google/gemini-3.8-flash', 'Gemini 3.8 Flash', 'high', 'high', '#6558c8', True, True),
        ('openai/gpt-6-luna', 'GPT-6 Luna', 'xhigh', 'high', '#9b4fc2', True, False),
        ('openai/gpt-6.1-sol', 'GPT-6.1 Sol', 'max', 'low', '#c3486b', True, False),
        ('openai/gpt-6-astra', 'GPT-6 Astra', 'max', 'low', '#c9269e', True, False),
        ('anthropic/claude-opus-5.5', 'Claude Opus 5.5', 'max', 'low', '#aea229', True, True),
    )
    return [dict(id=model + ('@high' if model == 'openai/gpt-6-luna' and effort == 'high' else ''),
                 model=model, label=label, tier=tier, reasoning_effort=effort, color=color,
                 vision=vision, temperature_supported=temperature, reasoning_supported=effort is not None,
                 enabled=True, supported_parameters=['reasoning'] if effort else [],
                 is_default=model == 'openai/gpt-6-luna' and effort == 'low',
                 metadata_source='bundled research configuration')
            for model, label, tier, effort, color, vision, temperature in definitions]


def validate_catalog(catalog):
    if not isinstance(catalog, list) or not 1 <= len(catalog) <= 32:
        raise ValueError('Keep between 1 and 32 model choices.')
    result, ids = [], set()
    for item in catalog:
        if not isinstance(item, dict):
            raise ValueError('Each model choice must be an object.')
        model, ident = str(item.get('model', '')).strip(), str(item.get('id', '')).strip()
        if not re.fullmatch(r'[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.:/-]+', model) or model.startswith(('ollama/', 'openrouter/')):
            raise ValueError('Choose an explicit cloud model identifier, not a router or local alias.')
        if not re.fullmatch(r'[a-zA-Z0-9_./:@-]{1,240}', ident) or ident in ids:
            raise ValueError('Every choice needs a unique identifier.')
        ids.add(ident)
        label = str(item.get('label') or model).strip()
        if not 1 <= len(label) <= 120 or item.get('tier') not in TIERS:
            raise ValueError('Provide a short name and valid experimental tier.')
        effort = item.get('reasoning_effort')
        if effort not in EFFORTS or effort is not None and not item.get('reasoning_supported'):
            raise ValueError('Choose a supported reasoning setting.')
        color = str(item.get('color', ''))
        if not re.fullmatch(r'#[a-fA-F0-9]{6}', color):
            raise ValueError('Choose a valid model color.')
        parameters = item.get('supported_parameters') or []
        if not isinstance(parameters, list) or len(parameters) > 60 or any(not isinstance(p, str) or len(p) > 80 for p in parameters):
            raise ValueError('Invalid capability metadata.')
        result.append({**{key: item.get(key) for key in ('context_length', 'max_completion_tokens', 'metadata_source', 'metadata_checked_at')},
                       'id': ident, 'model': model, 'label': label, 'tier': item['tier'],
                       'reasoning_effort': effort, 'color': color, 'enabled': item.get('enabled', True) is True,
                       'is_default': item.get('is_default') is True,
                       'vision': item.get('vision') is True, 'temperature_supported': item.get('temperature_supported') is True,
                       'reasoning_supported': item.get('reasoning_supported') is True, 'supported_parameters': parameters})
    if not any(item['enabled'] for item in result):
        raise ValueError('Keep at least one enabled model choice.')
    defaults = [item for item in result if item['is_default']]
    if len(defaults) > 1 or defaults and not defaults[0]['enabled']:
        raise ValueError('Choose only one enabled default model.')
    return result


def configured_catalog(settings=None):
    raw = (settings or {}).get(CATALOG_SETTING)
    return validate_catalog(json.loads(raw)) if raw else default_catalog()


def model_choices(settings=None):
    from local_llm import local_choice
    local = local_choice(settings or {})
    choices = []
    for item in configured_catalog(settings):
        if not item['enabled']:
            continue
        effort = item['reasoning_effort']
        suffix = ' · ' + ('Light' if effort == 'low' else effort.title()) + ' reasoning' if effort else ''
        choices.append({**item, 'name': item['label'] + suffix})
    if local:
        local['model'] = local['id']
        local = {key: value for key, value in local.items() if key not in {'input_price', 'output_price', 'reference_cost', 'verified_date'}}
    return ([local] if local else []) + choices


def model_choice(ident, settings=None):
    for choice in model_choices(settings):
        if choice['id'] == ident:
            return choice
    raise ValueError('Choose an enabled model from the configured catalogue.')


def frozen_model_configuration(choice):
    # Saving a catalogue may add optional null metadata fields. Those do not
    # change the selected experimental configuration or its identity.
    snapshot = {**{key: value for key, value in choice.items() if value is not None}, 'schema_version': 1}
    snapshot['digest'] = hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return snapshot


def discover_models(settings):
    """Read metadata only on explicit request; never update experiments."""
    endpoint = settings['openrouter_base_url'].rstrip('/') + '/models'
    headers = {'Authorization': 'Bearer ' + settings['openrouter_api_key']} if settings.get('openrouter_api_key') else {}
    response = requests.get(endpoint, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json().get('data')
    if not isinstance(data, list) or len(data) > 10000:
        raise ValueError('Invalid provider model catalogue.')
    now = datetime.now(timezone.utc).isoformat()
    result = []
    for item in data:
        model, architecture = item.get('id', ''), item.get('architecture') or {}
        if not isinstance(model, str) or model.startswith('openrouter/') or 'text' not in (architecture.get('output_modalities') or ['text']):
            continue
        parameters = item.get('supported_parameters') or []
        result.append({'model': model, 'label': item.get('name') or model,
                       'vision': 'image' in (architecture.get('input_modalities') or []),
                       'temperature_supported': 'temperature' in parameters,
                       'reasoning_supported': 'reasoning' in parameters or 'include_reasoning' in parameters,
                       'supported_parameters': parameters, 'context_length': item.get('context_length'),
                       'max_completion_tokens': (item.get('top_provider') or {}).get('max_completion_tokens'),
                       'metadata_source': endpoint, 'metadata_checked_at': now})
    return sorted(result, key=lambda item: item['label'].casefold())
