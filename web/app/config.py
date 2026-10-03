import os
from zoneinfo import ZoneInfo
from flask import Request, current_app
from settings import READONLY_MODEL_DEFAULTS


class ResearchRequest(Request):
    """Apply deployment byte limits on Flask 3.0 and newer releases alike."""

    @property
    def max_form_memory_size(self):
        return current_app.config["MAX_FORM_MEMORY_SIZE"]

    @property
    def max_form_parts(self):
        return current_app.config["MAX_FORM_PARTS"]


class Config:
    DOCUMENTATION_URL = "https://gverafei.github.io/web-accessibility-research-platform/"
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_DATASET_UPLOAD_BYTES", "3221225472"))
    # Large URL fields and multi-file corpora share the request byte budget;
    # they must not inherit Flask's 500 KB field / 1,000-part defaults.
    MAX_FORM_MEMORY_SIZE = MAX_CONTENT_LENGTH
    MAX_FORM_PARTS = None
    # Esta no se usa por el momento, pero es buena práctica tenerla para futuras configuraciones cuando se implemente un sistema de autenticación de usuarios.
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "accessibility-docker-platform-secret"
    )

    EVALUATOR_URL = os.getenv(
        "EVALUATOR_URL",
        "http://evaluator:3000"
    )

    APP_TIMEZONE = ZoneInfo(
        os.getenv("APP_TIMEZONE", "America/Mexico_City")
    )

    BABEL_DEFAULT_LOCALE = "en"
    BABEL_SUPPORTED_LOCALES = ("en", "es")
    BABEL_TRANSLATION_DIRECTORIES = "translations"

    OPENAI_MODEL = READONLY_MODEL_DEFAULTS['openai_model']
    GEMINI_MODEL = READONLY_MODEL_DEFAULTS['gemini_model']
    LLAMA_MODEL = READONLY_MODEL_DEFAULTS['llama_model']
    CLAUDE_MODEL = READONLY_MODEL_DEFAULTS['claude_model']
    KIMI_MODEL = READONLY_MODEL_DEFAULTS['kimi_model']
    QWEN_MODEL = READONLY_MODEL_DEFAULTS['qwen_model']
    MISTRAL_MODEL = READONLY_MODEL_DEFAULTS['mistral_model']
    OPENROUTER_API_KEY_CONFIGURED = bool(os.getenv("OPENROUTER_API_KEY", "").strip())
    OPENROUTER_BASE_URL_CONFIGURED = bool(os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip())
    WAVE_API_KEY_CONFIGURED = bool(os.getenv("WAVE_API_KEY", "").strip())

    DB_HOST = os.getenv("DB_HOST", "db")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_NAME = os.getenv("DB_NAME", "accessibility_experiments")
    DB_USER = os.getenv("DB_USER", "access_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "access_pass")
