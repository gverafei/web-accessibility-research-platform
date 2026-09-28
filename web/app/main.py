from flask import Flask, current_app, render_template, session
from flask_babel import Babel

from config import Config
from database import init_db
from routes.experiments import experiments_bp
from routes.comparisons import comparisons_bp
from routes.remediation import remediation_bp
from routes.extension_api import extension_api_bp
from routes.model_catalog import model_catalog_bp
from settings import get_settings


def select_locale():
    language = session.get("language", "en")
    supported = current_app.config["BABEL_SUPPORTED_LOCALES"]
    return language if language in supported else "en"


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    Babel(app, locale_selector=select_locale)

    @app.context_processor
    def inject_locale():
        try:
            ui_theme = session.get("ui_theme") or get_settings().get("ui_theme", "light")
        except Exception:
            ui_theme = "light"
        if ui_theme not in {"light", "dark", "system"}:
            ui_theme = "light"
        return {"current_locale": select_locale(), "ui_theme": ui_theme}

    with app.app_context():
        init_db()

    app.register_blueprint(experiments_bp)
    app.register_blueprint(comparisons_bp)
    app.register_blueprint(remediation_bp)
    app.register_blueprint(extension_api_bp)
    app.register_blueprint(model_catalog_bp)

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error("Unexpected application error", exc_info=error.original_exception or error)
        return render_template("error.html"), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
