"""Explicit catalogue administration; no model generation or implicit refresh."""
import json
import requests
from flask import Blueprint, jsonify, request
from remediation_model_choices import CATALOG_SETTING, configured_catalog, discover_models, validate_catalog
from settings import get_settings, save_settings

model_catalog_bp = Blueprint('model_catalog', __name__, url_prefix='/configuration/models')


@model_catalog_bp.get('/discover')
def discover():
    try:
        return jsonify(models=discover_models(get_settings()))
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return jsonify(error='Could not load the provider catalogue. Your saved choices were not changed.'), 502


@model_catalog_bp.get('')
def get_catalog():
    return jsonify(choices=configured_catalog(get_settings()))


@model_catalog_bp.post('')
def save_catalog():
    payload = request.get_json(silent=True) or {}
    try:
        choices = validate_catalog(payload.get('choices'))
    except (ValueError, TypeError) as error:
        return jsonify(error=str(error)), 400
    save_settings({CATALOG_SETTING: json.dumps(choices, ensure_ascii=False)})
    return jsonify(choices=choices, message='Saved. Existing runs retain their frozen model configuration.')
