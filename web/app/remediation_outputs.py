"""Strict output parsing: no invented repairs of truncated model responses."""
import json
import re


def parse_json_response(content):
    try:
        result=json.loads(content)
    except (ValueError,TypeError):
        match=re.search(r'(?s)\{.*\}',str(content or ''))
        if not match: raise ValueError('Model response did not contain a JSON object.')
        result=json.loads(match.group(0))
    if not isinstance(result,dict): raise ValueError('Model response must be a JSON object')
    return result
