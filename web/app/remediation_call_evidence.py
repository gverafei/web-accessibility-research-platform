"""Persist real model-call evidence independently of candidate validation."""
import hashlib
import json
from pathlib import Path


class RecordedModelCalls:
    def __init__(self, directory, runtime, caller):
        self.directory = Path(directory)
        self.runtime = runtime
        self.caller = caller
        self.records = []

    def checkpoint(self):
        document = {'schema_version': 'model-call-evidence-v1',
                    'calls': self.records, 'agentic_runtime': self.runtime.snapshot()}
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / 'model-call-evidence.json'
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(path)

    def __call__(self, settings, model, prompt, json_mode=False, temperature=None,
                 cost_tier=None, allowed_models=None, messages=None,
                 reasoning_override=None, output_token_limit=None):
        # Never persist settings: they contain provider credentials. Save the
        # exact inputs passed to the transport, including multimodal messages.
        record = {'call_number': len(self.records) + 1, 'stage': self.runtime.state,
                  'status': 'started', 'requested_model': model, 'prompt': prompt,
                  'messages': messages, 'json_mode': json_mode,
                  'temperature_requested': temperature, 'cost_tier': cost_tier,
                  'reasoning_override': reasoning_override,
                  'output_token_limit_requested': output_token_limit,
                  'model_configuration': settings.get('_model_configuration'),
                  'runtime_before_call': self.runtime.snapshot()}
        self.records.append(record)
        self.checkpoint()
        try:
            result = self.caller(settings, model, prompt, json_mode, temperature,
                                 cost_tier, allowed_models, messages,
                                 reasoning_override, output_token_limit)
        except Exception as error:
            # Usage is unknown when the transport does not return it, not zero.
            record.update(status='transport_failed', error_type=type(error).__name__)
            self.checkpoint()
            raise
        response, incoming, outgoing, cost, seconds, actual_model = result
        record.update(status='returned', response=response,
                      response_sha256=hashlib.sha256(response.encode('utf-8')).hexdigest(),
                      input_tokens=incoming, output_tokens=outgoing,
                      cost_usd=cost, seconds=seconds, actual_model=actual_model)
        self.checkpoint()
        return result
