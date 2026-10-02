import csv
import json
import os
import shutil
import tempfile
import zipfile
from math import ceil
from datetime import datetime
from io import StringIO
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from babel import Locale, UnknownLocaleError
from flask import (
    Blueprint,
    after_this_request,
    Response,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    send_file,
    url_for,
)
from flask_babel import gettext as _

from database import get_connection
from axe_metrics import project_wcag
from classify_site_categories import (
    CATEGORIES as WEBAIM_SITE_CATEGORIES,
    classify_managed_urls,
)
from remediation_approaches import approach_for
from remediation_recipes import common_conditions
from dataset_storage import (
    DatasetImportError, add_dataset_to_warp, clear_dataset_storage,
    import_dataset, import_dataset_from_warp, remove_dataset,
)
from result_portability import (
    ARTIFACT_COLUMNS,
    clone_result,
    decode_artifacts,
    encode_artifacts,
    ensure_http_scheme,
    evaluation_signature,
    json_value,
    normalize_url,
    validate_portable_payload,
)
from settings import (
    SETTING_DEFAULTS,
    DERIVED_SETTINGS,
    SECRET_SETTINGS,
    as_bool,
    evaluator_runtime_config,
    get_settings,
    save_settings,
)
from local_llm import local_configuration
from tranco_sampling import (
    TRANCO_STRATA, TrancoImportError, classify_failure, extend_ordered_reserves,
    fetch_latest_standard_list, fetch_pinned_standard_list, parse_tranco,
    plan_failed_replacements, sample_tranco,
)

import math
from statistics import mean, median, stdev

experiments_bp = Blueprint("experiments", __name__)

AXE_STANDARDS = {"wcag20a", "wcag20aa", "wcag21a", "wcag21aa", "wcag22a", "wcag22aa"}
MAX_EXPERIMENT_NAME = 160
TIMEZONE_GROUPS = (
    ("Universal", (("UTC", "UTC"),)),
    ("Mexico", (
        ("America/Mexico_City", "Mexico City — Central Mexico"),
        ("America/Mazatlan", "Mazatlan — Baja California Sur and northwest Mexico"),
        ("America/Tijuana", "Tijuana — Baja California"),
        ("America/Cancun", "Cancun — Quintana Roo"),
        ("America/Chihuahua", "Chihuahua"),
        ("America/Hermosillo", "Hermosillo — Sonora"),
    )),
    ("Americas", (
        ("America/Anchorage", "Anchorage"), ("Pacific/Honolulu", "Honolulu"),
        ("America/Los_Angeles", "Los Angeles / Vancouver"),
        ("America/Denver", "Denver"), ("America/Phoenix", "Phoenix"),
        ("America/Chicago", "Chicago"), ("America/New_York", "New York / Toronto"),
        ("America/Halifax", "Halifax"), ("America/St_Johns", "St. John's"),
        ("America/Bogota", "Bogota / Lima / Quito"),
        ("America/Caracas", "Caracas"), ("America/Santiago", "Santiago"),
        ("America/Sao_Paulo", "Sao Paulo"), ("America/Argentina/Buenos_Aires", "Buenos Aires"),
    )),
    ("Europe and Africa", (
        ("Atlantic/Azores", "Azores"), ("Europe/London", "London / Dublin"),
        ("Europe/Madrid", "Madrid / Paris / Berlin / Rome"),
        ("Europe/Athens", "Athens / Bucharest / Helsinki"),
        ("Europe/Moscow", "Moscow"), ("Africa/Casablanca", "Casablanca"),
        ("Africa/Cairo", "Cairo"), ("Africa/Johannesburg", "Johannesburg"),
        ("Africa/Nairobi", "Nairobi"),
    )),
    ("Asia", (
        ("Asia/Jerusalem", "Jerusalem"), ("Asia/Dubai", "Dubai"),
        ("Asia/Karachi", "Karachi"), ("Asia/Kolkata", "India / Sri Lanka"),
        ("Asia/Dhaka", "Dhaka"), ("Asia/Bangkok", "Bangkok / Jakarta"),
        ("Asia/Singapore", "Singapore / Kuala Lumpur"),
        ("Asia/Shanghai", "Beijing / Shanghai"), ("Asia/Hong_Kong", "Hong Kong"),
        ("Asia/Tokyo", "Tokyo / Seoul"),
    )),
    ("Oceania", (
        ("Australia/Perth", "Perth"), ("Australia/Adelaide", "Adelaide"),
        ("Australia/Brisbane", "Brisbane"), ("Australia/Sydney", "Sydney / Melbourne"),
        ("Pacific/Auckland", "Auckland"), ("Pacific/Fiji", "Fiji"),
    )),
)
TIMEZONE_CHOICES = {
    value for _group, choices in TIMEZONE_GROUPS for value, _label in choices
}
CLEAR_EXPERIMENTS_PHRASE = "DELETE ALL EXPERIMENTS"


def build_experiments_summary(experiments_data):
    return {
        "total_experiments": len(experiments_data),
        "completed_experiments": sum(item.get("status") == "completed" for item in experiments_data),
        "wave_experiments": sum(bool(item.get("include_wave")) for item in experiments_data),
        "processed_urls": sum(item.get("processed_urls") or 0 for item in experiments_data),
        "wave_credits": sum(item.get("wave_credits") or 0 for item in experiments_data),
        "total_cost": round(sum(float(item.get("total_cost") or 0) for item in experiments_data), 6),
    }


def now_local():
    timezone = ZoneInfo(get_settings()["app_timezone"])
    return datetime.now(timezone).replace(tzinfo=None)


@experiments_bp.route("/language/<language>", methods=["GET"])
def set_language(language):
    supported = current_app.config["BABEL_SUPPORTED_LOCALES"]
    if language not in supported:
        language = "en"

    session["language"] = language
    next_url = request.args.get("next", "")
    parsed = urlsplit(next_url)

    if parsed.scheme or parsed.netloc or not next_url.startswith("/"):
        next_url = url_for("experiments.index")

    return redirect(next_url)


@experiments_bp.route("/theme/<theme>", methods=["GET"])
def set_theme(theme):
    if theme not in {"light", "dark", "system"}:
        theme = "light"
    session["ui_theme"] = theme
    next_url = request.args.get("next", "")
    parsed = urlsplit(next_url)
    if parsed.scheme or parsed.netloc or not next_url.startswith("/"):
        next_url = url_for("experiments.index")
    return redirect(next_url)


@experiments_bp.route("/", methods=["GET"])
def index():
    conn=get_connection(); cursor=conn.cursor(dictionary=True)
    cursor.execute("""SELECT COUNT(*) total,SUM(status='completed') completed,
        SUM(status IN ('queued','running')) active,
        (SELECT COALESCE(SUM(cost_incurred_usd),0) FROM experiment_results) cost
        FROM experiments""")
    evaluations=cursor.fetchone() or {}
    cursor.execute("SELECT COUNT(*) pages,COALESCE(SUM(axe_wcag_violations),0) axe_issues,ROUND(AVG(lighthouse_score),1) lighthouse FROM experiment_results WHERE status='completed'")
    pages=cursor.fetchone() or {}
    cursor.execute("""SELECT COUNT(*) total,SUM(status='accepted') accepted,
        SUM(accepted_iteration_id IS NOT NULL) available,
        SUM(status IN ('queued','running')) active,COALESCE(SUM(total_cost_usd),0) cost
        FROM remediation_runs""")
    remediations=cursor.fetchone() or {}
    evaluation_cost=float(evaluations.get('cost') or 0)
    remediation_cost=float(remediations.get('cost') or 0)
    costs={"evaluation":evaluation_cost,"remediation":remediation_cost,
           "total":evaluation_cost+remediation_cost}
    cursor.execute("""SELECT generator_model model,COUNT(*) uses
        FROM remediation_iterations
        WHERE generator_model IS NOT NULL AND generator_model NOT LIKE 'system/%'
        GROUP BY generator_model ORDER BY uses DESC,model LIMIT 1""")
    most_used_model=cursor.fetchone() or {}
    cursor.execute("""SELECT accessibility_priority,COUNT(*) uses
        FROM remediation_runs GROUP BY accessibility_priority
        ORDER BY uses DESC,accessibility_priority LIMIT 1""")
    strategy_row=cursor.fetchone() or {}
    most_used_strategy={"name":approach_for(strategy_row.get('accessibility_priority')).name,
                        "uses":int(strategy_row.get('uses') or 0)} if strategy_row else {}
    cursor.execute("""SELECT ri.generator_model model,COUNT(*) runs,
        SUM(GREATEST(er.axe_wcag_violations-ri.axe_wcag_violations,0)) removed,
        SUM(rr.total_cost_usd) cost,
        SUM(GREATEST(er.axe_wcag_violations-ri.axe_wcag_violations,0))/SUM(rr.total_cost_usd) removed_per_dollar
        FROM remediation_runs rr
        JOIN remediation_iterations ri ON ri.id=rr.accepted_iteration_id
        JOIN experiment_results er ON er.id=rr.source_result_id
        WHERE rr.total_cost_usd>0 AND ri.generator_model IS NOT NULL
        AND ri.generator_model NOT LIKE 'system/%'
        AND ri.axe_wcag_violations IS NOT NULL AND er.axe_wcag_violations IS NOT NULL
        GROUP BY ri.generator_model HAVING removed>0
        ORDER BY removed_per_dollar DESC LIMIT 1""")
    value_model=cursor.fetchone() or {}
    cursor.execute("""SELECT ri.generator_model model,COUNT(*) runs,
        SUM(er.axe_wcag_violations) original_issues,
        SUM(GREATEST(er.axe_wcag_violations-ri.axe_wcag_violations,0)) removed,
        100*SUM(GREATEST(er.axe_wcag_violations-ri.axe_wcag_violations,0))/SUM(er.axe_wcag_violations) reduction_percent
        FROM remediation_runs rr
        JOIN remediation_iterations ri ON ri.id=rr.accepted_iteration_id
        JOIN experiment_results er ON er.id=rr.source_result_id
        WHERE ri.generator_model IS NOT NULL
        AND ri.generator_model NOT LIKE 'system/%'
        AND ri.axe_wcag_violations IS NOT NULL AND er.axe_wcag_violations>0
        GROUP BY ri.generator_model HAVING removed>0
        ORDER BY reduction_percent DESC,runs DESC LIMIT 1""")
    accessibility_model=cursor.fetchone() or {}
    insights={"most_used_model":most_used_model,"most_used_strategy":most_used_strategy,
              "value_model":value_model,"accessibility_model":accessibility_model}
    cursor.execute("SELECT id,title,status,created_at FROM experiments ORDER BY id DESC LIMIT 5")
    recent_evaluations=cursor.fetchall()
    cursor.execute("""SELECT rr.id,rr.title,rr.status,rr.progress_percent,rr.created_at,COALESCE(er.display_name,er.captured_url,er.url) page
        FROM remediation_runs rr JOIN experiment_results er ON er.id=rr.source_result_id ORDER BY rr.id DESC LIMIT 5""")
    recent_remediations=cursor.fetchall(); cursor.close(); conn.close()
    return render_template("dashboard.html",evaluations=evaluations,pages=pages,remediations=remediations,costs=costs,insights=insights,recent_evaluations=recent_evaluations,recent_remediations=recent_remediations)


@experiments_bp.route("/acquisition/new", methods=["GET"])
def new_acquisition():
    settings = get_settings()
    return render_template(
        "index.html",
        wave_available=bool(settings["wave_api_key"]),
    )


@experiments_bp.route("/configuration", methods=["GET", "POST"])
def configuration():
    from local_llm import local_configuration, installed_local_models
    settings = get_settings()
    if request.method == "POST":
        values = {}
        for key in SETTING_DEFAULTS:
            if key in DERIVED_SETTINGS:
                continue
            if key == 'remediation_model_catalog_json':
                continue  # Saved independently by the validated catalogue editor.
            if key in SECRET_SETTINGS:
                submitted = request.form.get(key, "").strip()
                values[key] = submitted or settings[key]
            elif key in {"axe_include_best_practices", "show_axe_failed_rules", "show_axe_needs_review", "show_axe_densities", "enable_lazy_load_scroll"}:
                values[key] = "true" if request.form.get(key) == "on" else "false"
            else:
                values[key] = request.form.get(key, settings[key]).strip()
        if values["axe_standard"] not in AXE_STANDARDS:
            values["axe_standard"] = "wcag22aa"
        values["wave_report_type"] = "2"
        try:
            common_conditions(values)
        except ValueError:
            flash(_("Remediation targets must be whole numbers: Lighthouse from 0 to 100 and Axe from 0 to 2147483647."), "danger")
            return redirect(url_for('experiments.configuration'))
        try:
            ZoneInfo(values["app_timezone"])
            if values["app_timezone"] not in TIMEZONE_CHOICES:
                raise ZoneInfoNotFoundError(values["app_timezone"])
        except ZoneInfoNotFoundError:
            values["app_timezone"] = settings["app_timezone"] if settings["app_timezone"] in TIMEZONE_CHOICES else "America/Mexico_City"
        try:
            config = local_configuration(values)
            capabilities = []
            if config:
                selected = next((item for item in installed_local_models(config['base_url']) if item['id'] == config['model']), None)
                if not selected:
                    raise ValueError('Select an installed local model.')
                capabilities = selected['capabilities']
            values['ollama_capabilities_json'] = json.dumps(capabilities)
        except (ValueError, requests.RequestException):
            flash(_('Could not save Ollama. Select an installed model from a reachable server, or clear both fields to disable it.'), 'danger')
            return redirect(url_for('experiments.configuration'))
        save_settings(values)
        flash(_("Configuration saved. New experiments will use these values."), "success")
        return redirect(url_for("experiments.configuration"))

    axe_version = "unknown"
    try:
        response = requests.get(f"{current_app.config['EVALUATOR_URL']}/health", timeout=3)
        response.raise_for_status()
        axe_version = response.json().get("axe_version", "unknown")
    except requests.RequestException:
        pass
    local_models = []
    local_models_error = False
    if settings.get('ollama_base_url'):
        try:
            local_models = installed_local_models(settings['ollama_base_url'])
        except (ValueError, requests.RequestException):
            local_models_error = True
    return render_template(
        "configuration.html",
        settings=settings,
        local_models=local_models,
        local_models_error=local_models_error,
        axe_version=axe_version,
        timezone_groups=TIMEZONE_GROUPS,
        clear_experiments_phrase=CLEAR_EXPERIMENTS_PHRASE,
    )


@experiments_bp.post('/configuration/test-ollama')
def test_ollama():
    from local_llm import local_configuration, installed_local_models
    try:
        config = local_configuration(get_settings())
        if not config:
            raise ValueError('Configure and save the Ollama server and model first.')
        installed = {item['id'] for item in installed_local_models(config['base_url'])}
        if config['model'] not in installed:
            raise ValueError('The configured model is not installed on this Ollama server.')
        flash(_('Ollama connection verified; the configured model is available. No generation was performed.'), 'success')
    except (ValueError, KeyError, requests.RequestException):
        flash(_('Could not verify Ollama. Check the saved server address, installed model and worker connectivity.'), 'danger')
    return redirect(url_for('experiments.configuration'))


@experiments_bp.post('/configuration/ollama-models')
def ollama_models():
    from local_llm import installed_local_models
    try:
        payload = request.get_json(silent=True) or {}
        return jsonify({'models': installed_local_models(payload.get('base_url'))})
    except (ValueError, requests.RequestException):
        return jsonify({'error': _('Could not load installed models. Check the Ollama server address and connectivity.')}), 400


@experiments_bp.route("/configuration/clear-experiments", methods=["POST"])
def clear_experiments():
    if request.form.get("confirmation_text", "") != CLEAR_EXPERIMENTS_PHRASE:
        flash(_("The confirmation text did not match. No experiments were deleted."), "warning")
        return redirect(url_for("experiments.configuration"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS total FROM experiments WHERE status IN ('queued', 'running')")
    active = int((cursor.fetchone() or {}).get("total") or 0)
    if active:
        cursor.close()
        conn.close()
        flash(_("Experiments cannot be cleared while an evaluation is queued or running."), "warning")
        return redirect(url_for("experiments.configuration"))

    try:
        cursor.execute("SELECT COUNT(*) AS total FROM experiments")
        total = int((cursor.fetchone() or {}).get("total") or 0)
        cursor.execute("DELETE FROM experiment_results")
        cursor.execute("DELETE FROM experiment_environment")
        cursor.execute("DELETE FROM experiments")
        cursor.execute("DELETE FROM dataset_observations")
        cursor.execute("DELETE FROM datasets")
        conn.commit()
        cursor.execute("ALTER TABLE experiments AUTO_INCREMENT = 1")
        cursor.execute("ALTER TABLE experiment_results AUTO_INCREMENT = 1")
        cursor.execute("ALTER TABLE experiment_environment AUTO_INCREMENT = 1")
        cursor.execute("ALTER TABLE dataset_observations AUTO_INCREMENT = 1")
        cursor.execute("ALTER TABLE datasets AUTO_INCREMENT = 1")
        cursor.execute("ALTER TABLE tranco_samples AUTO_INCREMENT = 1")
        conn.commit()
    except Exception:
        conn.rollback()
        flash(_("The experiments could not be cleared from the database."), "danger")
        return redirect(url_for("experiments.configuration"))
    finally:
        cursor.close()
        conn.close()

    clear_dataset_storage()

    files_removed = True
    results_root = os.path.realpath("/results/raw")
    if os.path.isdir(results_root):
        for name in os.listdir(results_root):
            path = os.path.realpath(os.path.join(results_root, name))
            if name.startswith("experiment_") and path.startswith(f"{results_root}{os.sep}") and os.path.isdir(path):
                try:
                    shutil.rmtree(path)
                except OSError:
                    files_removed = False

    if files_removed:
        flash(_("All %(count)s evaluation experiments and their generated files were deleted.", count=total), "success")
    else:
        flash(_("All database experiments were deleted, but some generated files could not be removed."), "warning")
    return redirect(url_for("experiments.configuration"))


@experiments_bp.route("/about", methods=["GET"])
def about():
    return render_template("about.html")


@experiments_bp.route("/experiments", methods=["GET"])
@experiments_bp.route("/evaluations", methods=["GET"])
def experiments():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT e.id, e.title, e.urls, e.include_wave, e.status, e.created_at,
               e.completed_at, e.experiment_origin, e.reuse_cached_results,
               e.source_type, e.resume_count, e.last_resumed_at,
               (SELECT COUNT(*) FROM experiment_results r WHERE r.experiment_id = e.id) AS processed_urls,
               (SELECT COUNT(*) FROM experiment_results r WHERE r.experiment_id = e.id AND r.status = 'completed') AS completed_urls,
               (SELECT COUNT(*) FROM experiment_results r WHERE r.experiment_id = e.id AND r.provenance <> 'fresh') AS reused_urls,
               (SELECT COUNT(*) FROM experiment_results r WHERE r.experiment_id = e.id AND r.status = 'failed') AS failed_urls,
               (SELECT COALESCE(SUM(r.wave_credits_used), 0) FROM experiment_results r WHERE r.experiment_id = e.id) AS wave_credits,
               (SELECT COALESCE(SUM(r.wave_cost_usd), 0) FROM experiment_results r WHERE r.experiment_id = e.id) AS total_cost,
               (SELECT COALESCE(SUM(r.execution_seconds), 0) FROM experiment_results r WHERE r.experiment_id = e.id) AS execution_seconds
        FROM experiments e
        ORDER BY id DESC
    """)

    all_experiments = cursor.fetchall()
    cursor.execute("SELECT experiment_id, candidates, strata FROM tranco_samples")
    recovery_ids = set()
    tranco_candidates = {}
    for sample in cursor.fetchall():
        candidates = sample.get("candidates") or []
        if isinstance(candidates, str):
            candidates = json.loads(candidates)
        strata = sample.get("strata") or []
        if isinstance(strata, str):
            strata = json.loads(strata)
        sample["target_size"] = sum(int(item.get("selected_count") or 0) for item in strata)
        tranco_candidates[sample["experiment_id"]] = {
            "candidates": candidates,
            "target_size": sample["target_size"],
        }
        if any(
            int(candidate.get("retry_count") or 0) > 0
            or candidate.get("role") in {"excluded_failed", "selected_replacement"}
            for candidate in candidates
        ):
            recovery_ids.add(sample["experiment_id"])
    tranco_ids = [item["id"] for item in all_experiments if item["id"] in tranco_candidates]
    result_urls = {experiment_id: set() for experiment_id in tranco_ids}
    if tranco_ids:
        placeholders = ",".join(["%s"] * len(tranco_ids))
        cursor.execute(
            f"SELECT experiment_id, url FROM experiment_results WHERE experiment_id IN ({placeholders})",
            tuple(tranco_ids),
        )
        for result in cursor.fetchall():
            result_urls[result["experiment_id"]].add(result["url"])
    for item in all_experiments:
        item["tranco_recovery"] = item["id"] in recovery_ids
        tranco_sample = tranco_candidates.get(item["id"])
        item["tranco_gap"] = max(
            0,
            int((tranco_sample or {}).get("target_size") or 0)
            - len([url for url in item["urls"].splitlines() if url.strip()]),
        )
        item["tranco_active_stratum"] = None
        if item["status"] in {"queued", "running"} and tranco_sample:
            stored_urls = result_urls.get(item["id"], set())
            pending_url = next(
                (url.strip() for url in item["urls"].splitlines()
                 if url.strip() and url.strip() not in stored_urls),
                None,
            )
            candidate = next(
                (value for value in tranco_sample["candidates"]
                 if value.get("url") == pending_url),
                None,
            )
            if candidate:
                item["tranco_active_stratum"] = (
                    candidate.get("stratum_name") or candidate.get("stratum")
                )
    query = request.args.get("q", "").strip()
    if query:
        needle = query.casefold()
        search_fields = (
            "title", "urls", "status", "experiment_origin",
        )
        experiments_data = [
            item for item in all_experiments
            if any(needle in str(item.get(field) or "").casefold() for field in search_fields)
        ]
    else:
        experiments_data = all_experiments

    cursor.close()
    conn.close()

    return render_template(
        "experiments.html",
        experiments=experiments_data,
        summary=build_experiments_summary(all_experiments),
        query=query,
    )


@experiments_bp.route("/experiments/<int:experiment_id>/title", methods=["POST"])
def rename_experiment(experiment_id):
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title") or "").strip()
    if not title or len(title) > MAX_EXPERIMENT_NAME:
        return jsonify({"ok": False, "error": _("Use a name between 1 and %(count)s characters.", count=MAX_EXPERIMENT_NAME)}), 400
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM experiments WHERE id=%s", (experiment_id,))
    if not cursor.fetchone():
        cursor.close(); conn.close()
        return jsonify({"ok": False, "error": _("The evaluation does not exist.")}), 404
    cursor.execute("UPDATE experiments SET title=%s WHERE id=%s", (title, experiment_id))
    conn.commit(); cursor.close(); conn.close()
    return jsonify({"ok": True, "title": title})


@experiments_bp.get("/urls/manage")
def manage_urls():
    # Return the usable shell immediately; rows are fetched independently.
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM url_category_jobs WHERE id=1")
    category_job = cursor.fetchone()
    cursor.close(); conn.close()
    settings = get_settings(); config = local_configuration(settings)
    return render_template(
        "manage_urls.html", site_categories=WEBAIM_SITE_CATEGORIES,
        category_model=(config or {}).get("model"),
        luna_available=bool(settings.get("openrouter_api_key")),
        category_job=category_job, uncategorized_count=0,
    )


@experiments_bp.get("/urls/manage/data")
def managed_urls_data():
    from managed_url_catalog import fetch_catalog_page
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    try:
        data = fetch_catalog_page(cursor, request.args)
        rows = data.pop("pages")
        data["html"] = render_template(
            "_managed_url_rows.html", pages=rows,
            site_categories=WEBAIM_SITE_CATEGORIES, offset=data["offset"],
        )
        return jsonify({"ok": True, **data})
    finally:
        cursor.close(); conn.close()


@experiments_bp.post("/urls/<int:result_id>/site-category")
def update_url_site_category(result_id):
    payload = request.get_json(silent=True) or request.form
    category = str(payload.get("site_category") or "").strip()
    if category not in WEBAIM_SITE_CATEGORIES:
        return jsonify({
            "ok": False,
            "error": _("Select a category from the WebAIM vocabulary."),
        }), 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id,normalized_url FROM experiment_results WHERE id=%s", (result_id,)
    )
    result = cursor.fetchone()
    if not result:
        cursor.close()
        conn.close()
        return jsonify({"ok": False, "error": _("The observation does not exist.")}), 404

    source = "manual · closed WebAIM 2026 vocabulary"
    if result.get("normalized_url"):
        cursor.execute(
            """UPDATE experiment_results
               SET site_category=%s,site_category_source=%s
               WHERE normalized_url=%s""",
            (category, source, result["normalized_url"]),
        )
    else:
        cursor.execute(
            """UPDATE experiment_results
               SET site_category=%s,site_category_source=%s WHERE id=%s""",
            (category, source, result_id),
        )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"ok": True, "site_category": category, "source": source})


@experiments_bp.post("/urls/auto-categorize")
def auto_categorize_managed_urls():
    settings = get_settings()
    config = local_configuration(settings)
    requested_model = str((request.get_json(silent=True) or {}).get("model") or "local")
    if requested_model not in ('local', 'luna'):
        return jsonify({'ok': False, 'error': _('Select an available category model.')}), 400
    if requested_model == "luna":
        if not settings.get("openrouter_api_key"):
            return jsonify({"ok": False, "error": _("Configure the OpenRouter API key before using GPT-6 Luna.")}), 400
        selected_model = "openai/gpt-6-luna"
    else:
        if not config:
            return jsonify({"ok": False, "error": _("Configure a local Ollama model before starting.")}), 400
        selected_model = "ollama/" + config["model"]
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM url_category_jobs WHERE id=1 FOR UPDATE")
    existing = cursor.fetchone()
    if existing and existing.get("status") in {"queued", "running", "stopping"}:
        cursor.close(); conn.close()
        return jsonify({"ok": True, "job": existing})
    raw_scope = (request.get_json(silent=True) or {}).get('experiment_id')
    try:
        scope_id = int(raw_scope) if raw_scope is not None else None
        if scope_id is not None and scope_id < 1:
            raise ValueError('Invalid scope')
    except (TypeError, ValueError):
        cursor.close(); conn.close()
        return jsonify({'ok': False, 'error': _('Invalid evaluation.')}), 400
    if scope_id:
        cursor.execute('SELECT status FROM experiments WHERE id=%s', (scope_id,))
        scoped = cursor.fetchone()
        if not scoped or scoped['status'] != 'completed':
            cursor.close(); conn.close()
            return jsonify({'ok': False, 'error': _('Wait until the evaluation is completed.')}), 400
    scope_sql = ' AND r.experiment_id=%s' if scope_id else ''
    cursor.execute(
        """SELECT COUNT(*) total FROM (
             SELECT r.site_category,ROW_NUMBER() OVER (
               PARTITION BY COALESCE(r.normalized_url,CONCAT('id:',r.id))
               ORDER BY COALESCE(r.evaluated_at,r.created_at) DESC,r.id DESC
             ) result_rank
             FROM experiment_results r WHERE r.status='completed'""" + scope_sql + """
           ) ranked WHERE result_rank=1 AND site_category IS NULL""",
        (scope_id,) if scope_id else (),
    )
    total = int((cursor.fetchone() or {}).get("total") or 0)
    if not total:
        cursor.close(); conn.close()
        return jsonify({"ok": True, "job": {"status": "completed", "total_urls": 0, "completed_urls": 0}})
    cursor.execute(
        """INSERT INTO url_category_jobs
           (id,status,total_urls,completed_urls,model,experiment_id,error_message,created_at,updated_at)
           VALUES (1,'queued',%s,0,%s,%s,NULL,NOW(),NOW())
           ON DUPLICATE KEY UPDATE status='queued',total_urls=VALUES(total_urls),
             completed_urls=0,model=VALUES(model),input_tokens=0,output_tokens=0,cost_usd=0,
             experiment_id=VALUES(experiment_id),error_message=NULL,created_at=NOW(),updated_at=NOW()""",
        (total, selected_model, scope_id),
    )
    conn.commit(); cursor.close(); conn.close()
    return jsonify({"ok": True, "job": {"status": "queued", "total_urls": total, "completed_urls": 0, "model": selected_model, "experiment_id": scope_id}})


@experiments_bp.get("/urls/auto-categorize/status")
def managed_url_categorization_status():
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM url_category_jobs WHERE id=1")
    job = cursor.fetchone() or {"status": "idle", "total_urls": 0, "completed_urls": 0}
    cursor.close(); conn.close()
    return jsonify({"ok": True, "job": job})


@experiments_bp.post("/urls/auto-categorize/stop")
def stop_managed_url_categorization():
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute(
        """UPDATE url_category_jobs SET status='stopping',updated_at=NOW()
           WHERE id=1 AND status IN ('queued','running')"""
    )
    conn.commit(); cursor.close(); conn.close()
    return jsonify({"ok": True})


@experiments_bp.route("/experiments/search-suggestions", methods=["GET"])
def experiment_search_suggestions():
    query = request.args.get("q", "").strip()
    like = f"%{query}%"
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT id, title, status, created_at
        FROM experiments
        WHERE %s = '' OR title LIKE %s OR urls LIKE %s OR status LIKE %s
              OR experiment_origin LIKE %s
        ORDER BY created_at DESC
        LIMIT 6
        """,
        (query, like, like, like, like),
    )
    experiments_found = cursor.fetchall()
    cursor.execute(
        """
        SELECT r.experiment_id, r.url, e.title
        FROM experiment_results r
        JOIN experiments e ON e.id = r.experiment_id
        WHERE %s <> '' AND r.url LIKE %s
        ORDER BY r.id DESC
        LIMIT 6
        """,
        (query, like),
    )
    urls_found = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify({
        "experiments": [
            {
                "id": item["id"], "title": item["title"],
                "status": item["status"], "date": str(item["created_at"]),
                "href": url_for("experiments.experiment_report", experiment_id=item["id"]),
            }
            for item in experiments_found
        ],
        "urls": [
            {
                "experiment_id": item["experiment_id"], "url": item["url"],
                "title": item["title"],
                "href": url_for("experiments.experiment_report", experiment_id=item["experiment_id"]) + "#url-results",
            }
            for item in urls_found
        ],
    })


@experiments_bp.route("/experiments/<int:experiment_id>/resume", methods=["POST"])
def resume_experiment(experiment_id):
    """Resume only the unfinished portion of an interrupted experiment."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id, status, urls FROM experiments WHERE id=%s FOR UPDATE",
            (experiment_id,),
        )
        experiment = cursor.fetchone()
        if not experiment:
            raise ValueError("missing")
        if experiment.get("status") not in {"failed", "paused"}:
            raise ValueError("not_resumable")
        cursor.execute(
            "SELECT COUNT(*) AS processed FROM experiment_results WHERE experiment_id=%s",
            (experiment_id,),
        )
        processed = int(cursor.fetchone()["processed"] or 0)
        total = len([url for url in (experiment.get("urls") or "").splitlines() if url.strip()])
        cursor.execute(
            """
            UPDATE experiments
            SET status='queued', completed_at=NULL,
                resume_count=resume_count+1, last_resumed_at=%s
            WHERE id=%s
            """,
            (now_local(), experiment_id),
        )
        conn.commit()
    except ValueError as error:
        conn.rollback()
        messages = {
            "missing": _("The requested evaluation experiment does not exist."),
            "not_resumable": _("Only a paused or failed experiment can be resumed."),
        }
        flash(messages[str(error)], "warning")
        return redirect(url_for("experiments.experiments"))
    except Exception:
        conn.rollback()
        flash(_("The experiment could not be resumed."), "danger")
        return redirect(url_for("experiments.experiments"))
    finally:
        cursor.close()
        conn.close()
    flash(
        _("Experiment resumed. %(processed)s stored result(s) were preserved and %(pending)s URL(s) remain pending.",
          processed=processed, pending=max(0, total - processed)),
        "success",
    )
    if request.form.get("return_to") == "list":
        return redirect(url_for("experiments.experiments"))
    return redirect(url_for("experiments.experiment_report", experiment_id=experiment_id))


@experiments_bp.route("/experiments/<int:experiment_id>/pause", methods=["POST"])
def pause_experiment(experiment_id):
    """Request a cooperative pause without discarding the current dataset."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id,status FROM experiments WHERE id=%s FOR UPDATE",
            (experiment_id,),
        )
        experiment = cursor.fetchone()
        if not experiment:
            raise ValueError("missing")
        if experiment.get("status") not in {"queued", "running"}:
            raise ValueError("not_active")
        cursor.execute(
            "UPDATE experiments SET status='paused', completed_at=NULL WHERE id=%s",
            (experiment_id,),
        )
        conn.commit()
    except ValueError as error:
        conn.rollback()
        messages = {
            "missing": _("The requested evaluation experiment does not exist."),
            "not_active": _("Only a queued or running experiment can be paused."),
        }
        flash(messages[str(error)], "warning")
        return redirect(url_for("experiments.experiments"))
    except Exception:
        conn.rollback()
        flash(_("The experiment could not be paused."), "danger")
        return redirect(url_for("experiments.experiments"))
    finally:
        cursor.close()
        conn.close()
    flash(_("Experiment paused. Stored results and sampling progress were preserved."), "success")
    if request.form.get("return_to") == "list":
        return redirect(url_for("experiments.experiments"))
    return redirect(url_for("experiments.experiment_report", experiment_id=experiment_id))


@experiments_bp.route("/experiments/compose", methods=["GET", "POST"])
def compose_experiment():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == "GET":
        selected_target_id = request.args.get("target", type=int)
        cursor.execute(
            """
            SELECT r.*, e.title AS source_title, e.created_at AS source_created_at,
                   e.axe_standard AS source_axe_standard, e.source_type AS experiment_source_type
            FROM experiment_results r
            JOIN experiments e ON e.id = r.experiment_id
            WHERE r.status = 'completed' AND e.status = 'completed'
            ORDER BY e.id DESC, COALESCE(r.evaluated_at, r.created_at) DESC, r.id DESC
            """
        )
        available_results = [project_wcag(row) for row in cursor.fetchall()]
        cursor.execute(
            "SELECT id, title, source_type FROM experiments WHERE status = 'completed' ORDER BY created_at DESC"
        )
        targets = cursor.fetchall()
        valid_target_ids = {item["id"] for item in targets}
        if selected_target_id not in valid_target_ids:
            selected_target_id = None
        selected_target = next(
            (item for item in targets if item["id"] == selected_target_id), None
        )
        target_results = []
        if selected_target_id:
            cursor.execute(
                """
                SELECT id, url, normalized_url, status, error_message, provenance, evaluated_at, created_at,
                       source_experiment_id, axe_wcag_violations AS axe_violations, lighthouse_score,
                       wave_status, wave_errors, semantic_status, display_name, dataset_observation_id
                FROM experiment_results WHERE experiment_id=%s ORDER BY id
                """,
                (selected_target_id,),
            )
            target_results = cursor.fetchall()
        cursor.execute(
            "SELECT experiment_id, normalized_url FROM experiment_results"
        )
        target_urls = {}
        for row in cursor.fetchall():
            target_urls.setdefault(str(row["experiment_id"]), []).append(
                row["normalized_url"]
            )
        cursor.close()
        conn.close()
        return render_template(
            "compose.html", available_results=available_results, targets=targets,
            target_urls=target_urls, selected_target_id=selected_target_id,
            selected_target=selected_target, target_results=target_results,
        )

    ajax_request = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    selected_ids = []
    for value in request.form.getlist("result_ids"):
        try:
            selected_ids.append(int(value))
        except ValueError:
            continue
    if not selected_ids:
        cursor.close()
        conn.close()
        if ajax_request:
            return jsonify({"ok": False, "message": _("Select at least one stored URL result.")}), 400
        flash(_("Select at least one stored URL result."), "warning")
        return redirect(url_for("experiments.compose_experiment"))

    placeholders = ",".join(["%s"] * len(selected_ids))
    cursor.execute(
        f"""
        SELECT r.*, e.include_wave AS source_include_wave,
               e.include_semantic AS source_include_semantic
        FROM experiment_results r JOIN experiments e ON e.id = r.experiment_id
        WHERE r.id IN ({placeholders}) AND r.status = 'completed'
        ORDER BY r.id
        """,
        selected_ids,
    )
    sources = cursor.fetchall()
    sources_by_id = {row["id"]: row for row in sources}
    sources = [sources_by_id[result_id] for result_id in selected_ids if result_id in sources_by_id]
    if not sources:
        cursor.close()
        conn.close()
        if ajax_request:
            return jsonify({"ok": False, "message": _("The selected stored results no longer exist.")}), 404
        flash(_("The selected stored results no longer exist."), "warning")
        return redirect(url_for("experiments.compose_experiment"))
    target_value = request.form.get("target_experiment", "new")
    replacement_artifacts = []
    added_rows = []
    try:
        if target_value == "new":
            title = request.form.get("title", "").strip() or _(
                "Combined evaluation %(timestamp)s",
                timestamp=now_local().strftime("%Y-%m-%d %H:%M:%S"),
            )
            if len(title) > MAX_EXPERIMENT_NAME:
                raise ValueError(_("Experiment names can contain at most %(count)s characters.", count=MAX_EXPERIMENT_NAME))
            include_wave = any(item.get("wave_status") == "completed" for item in sources)
            include_semantic = any(item.get("semantic_status") == "completed" for item in sources)
            urls = list(dict.fromkeys(item["url"] for item in sources))
            cursor.execute(
                """
                INSERT INTO experiments (
                    title, urls, include_semantic, include_wave, semantic_provider,
                    semantic_model, axe_standard, axe_include_best_practices,
                    reuse_cached_results, experiment_origin, language, status,
                    created_at, completed_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,FALSE,FALSE,'composed',%s,'completed',%s,%s)
                """,
                (
                    title, "\n".join(urls), include_semantic, include_wave,
                    "mixed" if include_semantic else None,
                    "mixed" if include_semantic else None,
                    "mixed", session.get("language", "en"), now_local(), now_local(),
                ),
            )
            target_id = cursor.lastrowid
        else:
            target_id = int(target_value)
            cursor.execute(
                "SELECT * FROM experiments WHERE id=%s AND status='completed'",
                (target_id,),
            )
            target = cursor.fetchone()
            if not target:
                raise ValueError("invalid target")

        cursor.execute(
            "SELECT normalized_url FROM experiment_results WHERE experiment_id=%s",
            (target_id,),
        )
        existing = {row["normalized_url"] for row in cursor.fetchall()}
        added = 0
        replaced = 0
        replace_existing = request.form.get("replace_existing") == "true"
        for source in sources:
            normalized = normalize_url(source.get("url"))
            was_replaced = False
            if normalized in existing:
                if not replace_existing or source.get("experiment_id") == target_id:
                    continue
                cursor.execute(
                    f"""SELECT id, {', '.join(ARTIFACT_COLUMNS)} FROM experiment_results
                        WHERE experiment_id=%s AND normalized_url=%s""",
                    (target_id, normalized),
                )
                replaced_rows = cursor.fetchall()
                for row in replaced_rows:
                    replacement_artifacts.extend(
                        row.get(column) for column in ARTIFACT_COLUMNS if row.get(column)
                    )
                cursor.execute(
                    "DELETE FROM experiment_results WHERE experiment_id=%s AND normalized_url=%s",
                    (target_id, normalized),
                )
                existing.discard(normalized)
                replaced += len(replaced_rows)
                was_replaced = bool(replaced_rows)
            cloned_id = clone_result(cursor, source, target_id, "composed")
            existing.add(normalized)
            added += 1
            added_rows.append({
                "id": cloned_id, "url": source.get("url"), "normalized_url": normalized,
                "display_name": source.get("display_name") or source.get("url"),
                "status": source.get("status"),
                "axe_violations": project_wcag(source).get("axe_violations"),
                "lighthouse_score": source.get("lighthouse_score"),
                "evaluated_at": str(source.get("evaluated_at") or source.get("created_at") or ""),
                "provenance": "composed",
                "source_experiment_id": source.get("source_experiment_id") or source.get("experiment_id"),
                "replaced": was_replaced,
            })

        cursor.execute(
            "SELECT url, wave_status, semantic_status FROM experiment_results WHERE experiment_id=%s ORDER BY id",
            (target_id,),
        )
        combined_rows = cursor.fetchall()
        cursor.execute(
            """
            UPDATE experiments SET urls=%s, include_wave=%s, include_semantic=%s,
                experiment_origin='composed', evaluation_signature=NULL, completed_at=%s
            WHERE id=%s
            """,
            (
                "\n".join(row["url"] for row in combined_rows),
                any(row.get("wave_status") == "completed" for row in combined_rows),
                any(row.get("semantic_status") == "completed" for row in combined_rows),
                now_local(), target_id,
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        cursor.close()
        conn.close()
        if ajax_request:
            return jsonify({"ok": False, "message": _("The selected results could not be combined.")}), 500
        flash(_("The selected results could not be combined."), "danger")
        return redirect(url_for("experiments.compose_experiment"))
    cursor.close()
    conn.close()
    target_directory = os.path.realpath(f"/results/raw/experiment_{target_id}")
    for path in replacement_artifacts:
        resolved = os.path.realpath(path)
        if resolved.startswith(f"{target_directory}{os.sep}"):
            try:
                if os.path.isfile(resolved):
                    os.remove(resolved)
            except OSError:
                pass
    if ajax_request:
        return jsonify({"ok": True, "target_id": target_id, "added": added, "replaced": replaced, "results": added_rows})
    if added:
        if replaced:
            flash(_("%(count)s stored URL result(s) were added; %(replaced)s existing result(s) were replaced.", count=added, replaced=replaced), "success")
        else:
            flash(_("%(count)s stored URL result(s) were added.", count=added), "success")
    else:
        flash(_("No results were added because every selected URL already exists in the destination experiment."), "warning")
    return redirect(url_for("experiments.experiment_report", experiment_id=target_id))


@experiments_bp.route("/experiments/<int:experiment_id>/json", methods=["GET"])
def download_experiment_json(experiment_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM experiments WHERE id=%s", (experiment_id,))
    experiment = cursor.fetchone()
    if not experiment:
        cursor.close()
        conn.close()
        flash(_("The requested evaluation experiment does not exist."), "warning")
        return redirect(url_for("experiments.experiments"))
    cursor.execute("SELECT * FROM experiment_environment WHERE experiment_id=%s ORDER BY id", (experiment_id,))
    environment = cursor.fetchall()
    cursor.execute("SELECT * FROM experiment_results WHERE experiment_id=%s ORDER BY id", (experiment_id,))
    results = cursor.fetchall()
    cursor.execute("SELECT * FROM tranco_samples WHERE experiment_id=%s", (experiment_id,))
    tranco_sample = cursor.fetchone()
    dataset = None
    observations = []
    if experiment.get("dataset_id"):
        cursor.execute("SELECT * FROM datasets WHERE id=%s", (experiment["dataset_id"],))
        dataset = cursor.fetchone()
        cursor.execute("SELECT * FROM dataset_observations WHERE dataset_id=%s ORDER BY id", (experiment["dataset_id"],))
        observations = cursor.fetchall()
    cursor.close()
    conn.close()
    portable_results = []
    for result in results:
        data = {key: json_value(value) for key, value in result.items() if key not in ARTIFACT_COLUMNS}
        portable_results.append({"data": data, "artifacts": encode_artifacts(result)})
    payload = {
        "format": "warp-experiment",
        "version": 3,
        "exported_at": now_local().isoformat(),
        "experiment": {key: json_value(value) for key, value in experiment.items()},
        "environment": [{key: json_value(value) for key, value in row.items()} for row in environment],
        "results": portable_results,
    }
    if dataset:
        payload["dataset"] = {
            "title": dataset["title"], "content_sha256": dataset["content_sha256"],
            "resource_policy": dataset["resource_policy"],
            "observations": [
                {
                    "source_id": row["id"],
                    "path": row["relative_path"], "observation_id": row["observation_key"],
                    "pair_id": row["pair_key"], "condition": row["condition_label"],
                    "stratum": row["stratum"], "expected_label": row["expected_label"],
                    "display_name": row.get("display_name"),
                    "content_sha256": row["content_sha256"],
                } for row in observations
            ],
        }
    if tranco_sample:
        payload["tranco_sample"] = {
            key: json_value(value) for key, value in tranco_sample.items()
            if key not in {"id", "experiment_id"}
        }
    temporary = tempfile.NamedTemporaryFile(prefix="warp-export-", suffix=".warp", delete=False)
    temporary.close()
    with zipfile.ZipFile(temporary.name, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("experiment.json", json.dumps(payload, ensure_ascii=False, indent=2))
        if dataset:
            add_dataset_to_warp(archive, dataset["storage_key"])

    @after_this_request
    def remove_export_file(response):
        try:
            os.remove(temporary.name)
        except OSError:
            pass
        return response

    return send_file(
        temporary.name, mimetype="application/vnd.warp+zip", as_attachment=True,
        download_name=f"experiment-{experiment_id}.warp",
    )


@experiments_bp.route("/experiments/<int:experiment_id>/tranco-sample.csv", methods=["GET"])
def download_tranco_sample(experiment_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM tranco_samples WHERE experiment_id=%s", (experiment_id,))
    sample = cursor.fetchone()
    cursor.close()
    conn.close()
    if not sample:
        flash(_("The requested experiment does not contain a Tranco sample."), "warning")
        return redirect(url_for("experiments.experiment_report", experiment_id=experiment_id))
    candidates = sample.get("candidates") or []
    if isinstance(candidates, str):
        candidates = json.loads(candidates)
    output = StringIO()
    fields = [
        "list_id", "list_sha256", "sampling_seed", "rank", "domain", "url",
        "stratum", "stratum_name", "role", "selection_order",
        "retry_count", "last_failure_message", "replaces", "replaced_by",
        "exclusion_category", "exclusion_reason",
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for candidate in candidates:
        writer.writerow({
            "list_id": sample["list_id"], "list_sha256": sample["list_sha256"],
            "sampling_seed": sample["sampling_seed"],
            **{key: candidate.get(key) for key in fields[3:]},
        })
    return Response(
        output.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=experiment-{experiment_id}-tranco-sample.csv"},
    )


@experiments_bp.route("/experiments/<int:experiment_id>/tranco-retry-failed", methods=["POST"])
def retry_failed_tranco_sites(experiment_id):
    """Retry each failed active Tranco candidate once before reserve substitution."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    artifacts = []
    retry_count = 0
    try:
        cursor.execute("SELECT * FROM experiments WHERE id=%s FOR UPDATE", (experiment_id,))
        experiment = cursor.fetchone()
        if not experiment or experiment.get("source_type") != "tranco":
            raise ValueError("not_tranco")
        if experiment.get("status") in {"queued", "running"}:
            raise ValueError("active")
        cursor.execute(
            "SELECT * FROM tranco_samples WHERE experiment_id=%s FOR UPDATE",
            (experiment_id,),
        )
        sample = cursor.fetchone()
        candidates = sample.get("candidates") if sample else []
        if isinstance(candidates, str):
            candidates = json.loads(candidates)
        active = {
            item.get("url"): item for item in candidates
            if item.get("role") in {"selected", "selected_replacement"}
        }
        cursor.execute(
            "SELECT * FROM experiment_results WHERE experiment_id=%s AND status='failed' ORDER BY id",
            (experiment_id,),
        )
        for row in cursor.fetchall():
            candidate = active.get(row.get("url"))
            if not candidate or int(candidate.get("retry_count") or 0) >= 1:
                continue
            artifacts.extend(
                row.get(column) for column in ARTIFACT_COLUMNS if row.get(column)
            )
            candidate["retry_count"] = 1
            candidate["last_failure_message"] = row.get("error_message")
            cursor.execute("DELETE FROM experiment_results WHERE id=%s", (row["id"],))
            retry_count += 1
        if not retry_count:
            raise ValueError("no_retry")
        cursor.execute(
            "UPDATE tranco_samples SET candidates=%s WHERE experiment_id=%s",
            (json.dumps(candidates), experiment_id),
        )
        cursor.execute(
            "UPDATE experiments SET status='queued', completed_at=NULL WHERE id=%s",
            (experiment_id,),
        )
        conn.commit()
    except ValueError as error:
        conn.rollback()
        messages = {
            "not_tranco": _("The requested experiment does not contain a Tranco sample."),
            "active": _("Wait for the active evaluation to finish before retrying sites."),
            "no_retry": _("No failed sampled sites are awaiting their single retry."),
        }
        flash(messages.get(str(error), _("The failed sites could not be retried.")), "warning")
        return redirect(url_for("experiments.experiment_report", experiment_id=experiment_id))
    except Exception:
        conn.rollback()
        flash(_("The failed sites could not be retried."), "danger")
        return redirect(url_for("experiments.experiment_report", experiment_id=experiment_id))
    finally:
        cursor.close()
        conn.close()

    result_directory = os.path.realpath(f"/results/raw/experiment_{experiment_id}")
    for path in artifacts:
        resolved = os.path.realpath(path)
        if resolved.startswith(f"{result_directory}{os.sep}") and os.path.isfile(resolved):
            try:
                os.remove(resolved)
            except OSError:
                pass
    flash(
        _("%(count)s failed site(s) were queued for one controlled retry.", count=retry_count),
        "success",
    )
    return redirect(url_for("experiments.experiment_report", experiment_id=experiment_id))


@experiments_bp.post("/experiments/<int:experiment_id>/tranco-fill-missing")
def fill_missing_tranco_sites(experiment_id):
    """Restore manually curated Tranco gaps with deterministic same-stratum reserves."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    replacements = []
    try:
        cursor.execute("SELECT * FROM experiments WHERE id=%s FOR UPDATE", (experiment_id,))
        experiment = cursor.fetchone()
        if not experiment or experiment.get("source_type") != "tranco":
            raise ValueError("not_tranco")
        if experiment.get("status") in {"queued", "running"}:
            raise ValueError("active")
        cursor.execute(
            "SELECT * FROM tranco_samples WHERE experiment_id=%s FOR UPDATE",
            (experiment_id,),
        )
        sample = cursor.fetchone()
        if not sample:
            raise ValueError("not_tranco")
        candidates = sample.get("candidates") or []
        if isinstance(candidates, str):
            candidates = json.loads(candidates)
        current_urls = [url.strip() for url in experiment["urls"].splitlines() if url.strip()]
        current_keys = {normalize_url(url) for url in current_urls}
        missing = [
            candidate for candidate in candidates
            if candidate.get("role") in {"selected", "selected_replacement"}
            and normalize_url(candidate.get("url")) not in current_keys
        ]
        if not missing:
            raise ValueError("no_gaps")

        needed = {}
        for candidate in missing:
            label = candidate.get("stratum")
            needed[label] = needed.get(label, 0) + 1
        available = {}
        for candidate in candidates:
            if candidate.get("role") == "reserve":
                label = candidate.get("stratum")
                available[label] = available.get(label, 0) + 1
        exhausted = {
            label for label, count in needed.items() if available.get(label, 0) < count
        }
        if exhausted:
            list_bytes, filename = fetch_pinned_standard_list(sample["list_id"])
            ranking, metadata = parse_tranco(list_bytes, filename)
            if metadata["list_sha256"] != sample["list_sha256"]:
                raise TrancoImportError("The pinned Tranco list digest changed.")
            extend_ordered_reserves(
                ranking, sample["list_id"], sample["sampling_seed"], candidates,
                exhausted,
            )

        reserves = {}
        for candidate in candidates:
            if candidate.get("role") == "reserve":
                reserves.setdefault(candidate.get("stratum"), []).append(candidate)
        for pool in reserves.values():
            pool.sort(key=lambda item: int(item.get("selection_order") or 0))
        for removed in missing:
            pool = reserves.get(removed.get("stratum"), [])
            if not pool:
                raise TrancoImportError(
                    f"No reserve remains for {removed.get('stratum')}."
                )
            reserve = pool.pop(0)
            removed["role"] = "excluded_curated"
            removed["exclusion_category"] = "manual_curation"
            removed["exclusion_reason"] = "Removed during visual dataset curation"
            removed["replaced_by"] = reserve["url"]
            reserve["role"] = "selected_replacement"
            reserve["replaces"] = removed["url"]
            reserve["selection_cohort"] = "manual_curation"
            current_urls.append(reserve["url"])
            replacements.append((removed["url"], reserve["url"]))

        cursor.execute(
            "UPDATE tranco_samples SET candidates=%s WHERE experiment_id=%s",
            (json.dumps(candidates), experiment_id),
        )
        cursor.execute(
            "UPDATE experiments SET urls=%s,status='queued',completed_at=NULL WHERE id=%s",
            ("\n".join(current_urls), experiment_id),
        )
        conn.commit()
    except ValueError as error:
        conn.rollback()
        messages = {
            "not_tranco": _("The requested evaluation does not contain a Tranco sample."),
            "active": _("Wait for the active evaluation to finish before filling missing URLs."),
            "no_gaps": _("This evaluation has no missing sampled URLs."),
        }
        flash(messages.get(str(error), _("The missing URLs could not be filled.")), "warning")
    except Exception as error:
        conn.rollback()
        current_app.logger.exception("Could not fill Tranco gaps for experiment %s", experiment_id)
        flash(_("The missing URLs could not be filled: %(error)s", error=str(error)), "danger")
    finally:
        cursor.close()
        conn.close()

    if replacements:
        flash(_(
            "%(count)s missing URL(s) were filled with the next reserves from the same popularity groups.",
            count=len(replacements),
        ), "success")
    return redirect(url_for("experiments.experiments"))


@experiments_bp.route("/experiments/<int:experiment_id>/tranco-replace-failed", methods=["POST"])
def replace_failed_tranco_sites(experiment_id):
    """Replace failed sampled sites with the next recorded reserve in each stratum."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    artifacts = []
    try:
        cursor.execute(
            "SELECT * FROM experiments WHERE id=%s FOR UPDATE", (experiment_id,)
        )
        experiment = cursor.fetchone()
        if not experiment or experiment.get("source_type") != "tranco":
            raise ValueError("not_tranco")
        if experiment.get("status") in {"queued", "running"}:
            raise ValueError("active")
        cursor.execute(
            "SELECT * FROM tranco_samples WHERE experiment_id=%s FOR UPDATE",
            (experiment_id,),
        )
        sample = cursor.fetchone()
        candidates = sample.get("candidates") if sample else []
        if isinstance(candidates, str):
            candidates = json.loads(candidates)
        cursor.execute(
            "SELECT * FROM experiment_results WHERE experiment_id=%s AND status='failed' ORDER BY id",
            (experiment_id,),
        )
        failed_rows = cursor.fetchall()
        failed_by_url = {row["url"]: row for row in failed_rows}
        replacements = plan_failed_replacements(candidates, failed_by_url)
        if not replacements:
            raise ValueError("no_replacements")

        urls = [item.strip() for item in experiment["urls"].splitlines() if item.strip()]
        for failed_candidate, reserve in replacements:
            failed_url = failed_candidate["url"]
            failed_row = failed_by_url[failed_url]
            artifacts.extend(
                failed_row.get(column) for column in ARTIFACT_COLUMNS
                if failed_row.get(column)
            )
            cursor.execute("DELETE FROM experiment_results WHERE id=%s", (failed_row["id"],))
            urls = [reserve["url"] if value == failed_url else value for value in urls]
            failed_candidate["role"] = "excluded_failed"
            failed_candidate["exclusion_reason"] = failed_row.get("error_message") or "evaluation_failed"
            failed_candidate["exclusion_category"] = classify_failure(
                failed_row.get("error_message")
            )
            failed_candidate["replaced_by"] = reserve["url"]
            reserve["role"] = "selected_replacement"
            reserve["replaces"] = failed_url

        cursor.execute(
            "UPDATE tranco_samples SET candidates=%s WHERE experiment_id=%s",
            (json.dumps(candidates), experiment_id),
        )
        cursor.execute(
            "UPDATE experiments SET urls=%s, status='queued', completed_at=NULL WHERE id=%s",
            ("\n".join(urls), experiment_id),
        )
        conn.commit()
    except ValueError as error:
        conn.rollback()
        messages = {
            "not_tranco": _("The requested experiment does not contain a Tranco sample."),
            "active": _("Wait for the active evaluation to finish before replacing sites."),
            "no_replacements": _("No failed sampled sites have an unused reserve in the same stratum."),
        }
        flash(messages.get(str(error), _("The failed sites could not be replaced.")), "warning")
        return redirect(url_for("experiments.experiment_report", experiment_id=experiment_id))
    except Exception:
        conn.rollback()
        flash(_("The failed sites could not be replaced."), "danger")
        return redirect(url_for("experiments.experiment_report", experiment_id=experiment_id))
    finally:
        cursor.close()
        conn.close()

    result_directory = os.path.realpath(f"/results/raw/experiment_{experiment_id}")
    for path in artifacts:
        resolved = os.path.realpath(path)
        if resolved.startswith(f"{result_directory}{os.sep}") and os.path.isfile(resolved):
            try:
                os.remove(resolved)
            except OSError:
                pass
    flash(
        _("%(count)s failed site(s) were replaced with the next reserve in the same stratum. The replacement evaluation was queued.", count=len(replacements)),
        "success",
    )
    return redirect(url_for("experiments.experiment_report", experiment_id=experiment_id))


@experiments_bp.route("/experiments/import", methods=["GET", "POST"])
def import_experiment_json():
    if request.method == "GET":
        return render_template("import.html")

    upload = request.files.get("experiment_file")
    if not upload:
        flash(_("Select an exported .warp experiment file."), "warning")
        return redirect(url_for("experiments.import_experiment_json"))
    try:
        if not (upload.filename or "").lower().endswith(".warp"):
            raise ValueError("invalid extension")
        package = zipfile.ZipFile(upload.stream)
        package_members = [item for item in package.infolist() if not item.is_dir()]
        names = {item.filename for item in package_members}
        if "experiment.json" not in names or any(
            name.startswith("/") or ".." in name.replace("\\", "/").split("/")
            for name in names
        ) or any(name != "experiment.json" and not name.startswith("dataset/") for name in names):
            raise ValueError("invalid package")
        manifest_info = package.getinfo("experiment.json")
        if manifest_info.file_size > current_app.config["MAX_CONTENT_LENGTH"] or len(package_members) > 10_001:
            raise ValueError("package limits exceeded")
        payload = json.loads(package.read("experiment.json").decode("utf-8"))
        imported_results = validate_portable_payload(payload)
    except Exception:
        flash(_("The selected file is not a supported experiment export."), "danger")
        return redirect(url_for("experiments.import_experiment_json"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    target_value = "new"
    target_id = None
    files_before = set()
    imported_dataset_metadata = None
    observation_id_map = {}
    try:
        metadata = payload.get("experiment") or {}
        imported_dataset_id = None
        if payload.get("dataset"):
            imported_dataset_metadata, restored_observations = import_dataset_from_warp(
                package, payload["dataset"], payload["dataset"].get("title") or metadata.get("title") or "Imported dataset"
            )
            cursor.execute(
                """INSERT INTO datasets (title, storage_key, content_sha256, resource_policy,
                   observation_count, created_at) VALUES (%s,%s,%s,%s,%s,%s)""",
                (imported_dataset_metadata["title"], imported_dataset_metadata["storage_key"],
                 imported_dataset_metadata["content_sha256"], imported_dataset_metadata["resource_policy"],
                 len(restored_observations), now_local()),
            )
            imported_dataset_id = cursor.lastrowid
            descriptor_rows = payload["dataset"].get("observations") or []
            for descriptor, observation in zip(descriptor_rows, restored_observations):
                cursor.execute(
                    """INSERT INTO dataset_observations (
                       dataset_id, relative_path, observation_key, pair_key, condition_label,
                       stratum, expected_label, content_sha256, served_url, display_name, created_at
                       ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (imported_dataset_id, observation["path"], observation["observation_id"],
                     observation["pair_id"] or None, observation["condition"] or None,
                     observation["stratum"] or None,
                     int(observation["expected_label"]) if observation["expected_label"] else None,
                     observation["content_sha256"], observation["served_url"],
                     observation.get("display_name"), now_local()),
                )
                observation_id_map[descriptor.get("source_id")] = {
                    "id": cursor.lastrowid, "url": observation["served_url"],
                    "hash": observation["content_sha256"],
                }
        if target_value == "new":
            title = request.form.get("import_title", "").strip() or f"{metadata.get('title', 'Imported evaluation')} (import)"
            cursor.execute(
                """
                INSERT INTO experiments (
                    title, urls, include_semantic, include_wave, semantic_provider,
                    semantic_model, axe_standard, axe_include_best_practices,
                    reuse_cached_results, experiment_origin, source_type, dataset_id,
                    resource_policy, language, status,
                    created_at, completed_at
                ) VALUES (%s,'',%s,%s,%s,%s,%s,%s,FALSE,'imported',%s,%s,%s,%s,'completed',%s,%s)
                """,
                (
                    title, bool(metadata.get("include_semantic")), bool(metadata.get("include_wave")),
                    metadata.get("semantic_provider"), metadata.get("semantic_model"),
                    metadata.get("axe_standard") or "mixed", bool(metadata.get("axe_include_best_practices")),
                    ("local_html" if imported_dataset_id else
                     "tranco" if isinstance(payload.get("tranco_sample"), dict) else "url"),
                    imported_dataset_id,
                    imported_dataset_metadata["resource_policy"] if imported_dataset_metadata else "external",
                    session.get("language", "en"), now_local(), now_local(),
                ),
            )
            target_id = cursor.lastrowid
        else:
            target_id = int(target_value)
            cursor.execute("SELECT id FROM experiments WHERE id=%s AND status='completed'", (target_id,))
            if not cursor.fetchone():
                raise ValueError("invalid target")

        imported_tranco = payload.get("tranco_sample")
        if target_value == "new" and isinstance(imported_tranco, dict):
            imported_strata = imported_tranco.get("strata") or []
            imported_candidates = imported_tranco.get("candidates") or []
            if isinstance(imported_strata, str):
                imported_strata = json.loads(imported_strata)
            if isinstance(imported_candidates, str):
                imported_candidates = json.loads(imported_candidates)
            cursor.execute(
                """
                INSERT INTO tranco_samples (
                    experiment_id, list_id, list_sha256, source_filename,
                    frame_size, sampling_seed, sample_per_stratum,
                    reserve_per_stratum, strata, candidates, created_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    target_id, imported_tranco.get("list_id"),
                    imported_tranco.get("list_sha256"),
                    imported_tranco.get("source_filename"),
                    imported_tranco.get("frame_size"),
                    imported_tranco.get("sampling_seed"),
                    imported_tranco.get("sample_per_stratum"),
                    imported_tranco.get("reserve_per_stratum"),
                    json.dumps(imported_strata),
                    json.dumps(imported_candidates), now_local(),
                ),
            )

        import_directory = os.path.realpath(f"/results/raw/experiment_{target_id}")
        if os.path.isdir(import_directory):
            files_before = set(os.listdir(import_directory))

        cursor.execute("SELECT normalized_url FROM experiment_results WHERE experiment_id=%s", (target_id,))
        existing = {row["normalized_url"] for row in cursor.fetchall()}
        added = 0
        for entry in imported_results:
            source = dict(entry.get("data") or {})
            restored = observation_id_map.get(source.get("dataset_observation_id"))
            if restored:
                source["dataset_observation_id"] = restored["id"]
                source["url"] = restored["url"]
                source["normalized_url"] = normalize_url(restored["url"])
                source["content_sha256"] = restored["hash"]
            normalized = normalize_url(source.get("url"))
            if not normalized or normalized in existing:
                continue
            source["id"] = source.get("id")
            source = decode_artifacts(source, entry.get("artifacts"), target_id)
            clone_result(cursor, source, target_id, "imported", copy_files=False)
            existing.add(normalized)
            added += 1
        cursor.execute("SHOW COLUMNS FROM experiment_environment")
        environment_columns = {
            row["Field"] for row in cursor.fetchall()
        }
        for imported_environment in payload.get("environment") or []:
            columns = [
                key for key in imported_environment
                if key in environment_columns and key not in {"id", "experiment_id"}
            ]
            if not columns:
                continue
            quoted = ", ".join(f"`{column}`" for column in columns)
            placeholders = ", ".join(["%s"] * len(columns))
            cursor.execute(
                f"INSERT INTO experiment_environment (`experiment_id`, {quoted}) VALUES (%s, {placeholders})",
                [target_id, *[imported_environment.get(column) for column in columns]],
            )
        cursor.execute("SELECT url, wave_status, semantic_status FROM experiment_results WHERE experiment_id=%s ORDER BY id", (target_id,))
        rows = cursor.fetchall()
        restored_urls = "\n".join(row["url"] for row in rows)
        original_urls = [
            value.strip() for value in str(metadata.get("urls") or "").splitlines()
            if value.strip()
        ]
        if (
            target_value == "new" and not imported_dataset_id and original_urls
            and {normalize_url(value) for value in original_urls}
            == {normalize_url(row["url"]) for row in rows}
        ):
            restored_urls = "\n".join(original_urls)
        cursor.execute(
            """UPDATE experiments SET urls=%s, include_wave=%s, include_semantic=%s,
               experiment_origin=IF(experiment_origin='evaluation','composed',experiment_origin),
               evaluation_signature=NULL, completed_at=%s WHERE id=%s""",
            (
                restored_urls,
                any(row.get("wave_status") == "completed" for row in rows),
                any(row.get("semantic_status") == "completed" for row in rows),
                now_local(), target_id,
            ),
        )
        conn.commit()
    except Exception:
        current_app.logger.exception("Portable experiment import failed")
        conn.rollback()
        if imported_dataset_metadata:
            remove_dataset(imported_dataset_metadata["storage_key"])
        cursor.close()
        conn.close()
        if target_id is not None:
            import_directory = os.path.realpath(f"/results/raw/experiment_{target_id}")
            if os.path.isdir(import_directory):
                for filename in set(os.listdir(import_directory)) - files_before:
                    path = os.path.realpath(os.path.join(import_directory, filename))
                    if path.startswith(f"{import_directory}{os.sep}") and os.path.isfile(path):
                        try:
                            os.remove(path)
                        except OSError:
                            pass
        flash(_("The experiment could not be imported."), "danger")
        return redirect(url_for("experiments.import_experiment_json"))
    cursor.close()
    conn.close()
    flash(_("%(count)s imported URL result(s) were added.", count=added), "success")
    return redirect(url_for("experiments.experiment_report", experiment_id=target_id))


@experiments_bp.route("/experiments/<int:experiment_id>/delete", methods=["POST"])
def delete_experiment(experiment_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, title, status FROM experiments WHERE id = %s",
        (experiment_id,),
    )
    experiment = cursor.fetchone()

    if not experiment:
        cursor.close()
        conn.close()
        flash(_("The requested evaluation experiment does not exist."), "warning")
        return redirect(url_for("experiments.experiments"))

    if experiment.get("status") in {"queued", "running"}:
        cursor.close()
        conn.close()
        flash(_("A running evaluation experiment cannot be deleted."), "warning")
        return redirect(url_for("experiments.experiments"))

    try:
        cursor.execute(
            "DELETE FROM experiment_results WHERE experiment_id = %s",
            (experiment_id,),
        )
        cursor.execute(
            "DELETE FROM experiment_environment WHERE experiment_id = %s",
            (experiment_id,),
        )
        cursor.execute("DELETE FROM experiments WHERE id = %s", (experiment_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        flash(_("The evaluation experiment could not be deleted from the database."), "danger")
        return redirect(url_for("experiments.experiments"))
    finally:
        cursor.close()
        conn.close()

    results_root = os.path.realpath("/results/raw")
    experiment_directory = os.path.realpath(
        os.path.join(results_root, f"experiment_{experiment_id}")
    )
    files_removed = True
    if experiment_directory.startswith(f"{results_root}{os.sep}") and os.path.isdir(experiment_directory):
        try:
            shutil.rmtree(experiment_directory)
        except OSError:
            files_removed = False

    if files_removed:
        flash(_("Evaluation experiment and all associated data were deleted."), "success")
    else:
        flash(
            _("The database records were deleted, but some generated files could not be removed."),
            "warning",
        )
    return redirect(url_for("experiments.experiments"))


@experiments_bp.route("/experiments/<int:experiment_id>/urls")
def manage_experiment_urls(experiment_id):
    return redirect(url_for("experiments.compose_experiment", target=experiment_id))


@experiments_bp.route("/experiments/<int:experiment_id>/urls/remove", methods=["POST"])
def remove_experiment_urls(experiment_id):
    try:
        selected_ids = sorted({int(value) for value in request.form.getlist("result_ids")})
    except (TypeError, ValueError):
        selected_ids = []
    if not selected_ids:
        flash(_("Select at least one URL result."), "warning")
        return redirect(url_for("experiments.compose_experiment", target=experiment_id))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    artifact_paths = []
    experiment_deleted = False
    try:
        cursor.execute(
            "SELECT id, status FROM experiments WHERE id = %s FOR UPDATE",
            (experiment_id,),
        )
        experiment = cursor.fetchone()
        if not experiment:
            flash(_("The requested evaluation experiment does not exist."), "warning")
            return redirect(url_for("experiments.experiments"))
        if experiment.get("status") in {"queued", "running"}:
            flash(_("URL results cannot be removed while an experiment is running."), "warning")
            return redirect(url_for("experiments.compose_experiment", target=experiment_id))

        placeholders = ", ".join(["%s"] * len(selected_ids))
        cursor.execute(
            f"""SELECT id, {', '.join(ARTIFACT_COLUMNS)}
                FROM experiment_results
                WHERE experiment_id = %s AND id IN ({placeholders})""",
            [experiment_id, *selected_ids],
        )
        selected = cursor.fetchall()
        cursor.execute(
            "SELECT COUNT(*) AS total FROM experiment_results WHERE experiment_id = %s",
            (experiment_id,),
        )
        total = cursor.fetchone()["total"]
        if not selected:
            flash(_("The selected URL results are no longer available."), "warning")
            return redirect(url_for("experiments.compose_experiment", target=experiment_id))
        for row in selected:
            artifact_paths.extend(row.get(column) for column in ARTIFACT_COLUMNS if row.get(column))
        selected_db_ids = [row["id"] for row in selected]
        if len(selected) >= total:
            cursor.execute("DELETE FROM experiment_results WHERE experiment_id = %s", (experiment_id,))
            cursor.execute("DELETE FROM experiment_environment WHERE experiment_id = %s", (experiment_id,))
            cursor.execute("DELETE FROM experiments WHERE id = %s", (experiment_id,))
            conn.commit()
            experiment_deleted = True
        else:
            delete_placeholders = ", ".join(["%s"] * len(selected_db_ids))
            cursor.execute(
                f"DELETE FROM experiment_results WHERE experiment_id = %s AND id IN ({delete_placeholders})",
                [experiment_id, *selected_db_ids],
            )
            cursor.execute(
                "SELECT url, wave_status, semantic_status FROM experiment_results WHERE experiment_id = %s ORDER BY id",
                (experiment_id,),
            )
            remaining = cursor.fetchall()
            cursor.execute(
                """UPDATE experiments
                   SET urls=%s, include_wave=%s, include_semantic=%s, evaluation_signature=NULL
                   WHERE id=%s""",
                (
                    "\n".join(row["url"] for row in remaining),
                    any(row.get("wave_status") == "completed" for row in remaining),
                    any(row.get("semantic_status") == "completed" for row in remaining),
                    experiment_id,
                ),
            )
            conn.commit()
    except Exception:
        conn.rollback()
        flash(_("The selected URL results could not be removed."), "danger")
        return redirect(url_for("experiments.compose_experiment", target=experiment_id))
    finally:
        cursor.close()
        conn.close()

    experiment_directory = os.path.realpath(f"/results/raw/experiment_{experiment_id}")
    files_removed = True
    if experiment_deleted:
        try:
            if os.path.isdir(experiment_directory):
                shutil.rmtree(experiment_directory)
        except OSError:
            files_removed = False
        if files_removed:
            flash(_("The experiment was deleted because all of its URL results were removed."), "success")
        else:
            flash(_("The experiment was deleted, but some generated files could not be removed."), "warning")
        return redirect(url_for("experiments.experiments"))

    for path in artifact_paths:
        resolved = os.path.realpath(path)
        if not resolved.startswith(f"{experiment_directory}{os.sep}"):
            continue
        try:
            if os.path.isfile(resolved):
                os.remove(resolved)
        except OSError:
            files_removed = False
    if files_removed:
        flash(_("%(count)s URL result(s) were removed from the experiment.", count=len(selected)), "success")
    else:
        flash(_("The URL results were removed, but some generated files could not be deleted."), "warning")
    return redirect(url_for("experiments.compose_experiment", target=experiment_id))

def safe_mean(values):
    values = [v for v in values if v is not None]
    return round(mean(values), 2) if values else 0


def safe_median(values):
    values = [v for v in values if v is not None]
    return round(median(values), 2) if values else 0


def safe_stdev(values):
    values = [v for v in values if v is not None]
    return round(stdev(values), 2) if len(values) > 1 else 0


def pearson_correlation(x_values, y_values):
    pairs = [
        (x, y) for x, y in zip(x_values, y_values)
        if x is not None and y is not None
    ]

    if len(pairs) < 2:
        return None

    x = [p[0] for p in pairs]
    y = [p[1] for p in pairs]

    x_mean = mean(x)
    y_mean = mean(y)

    numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in pairs)
    denominator_x = math.sqrt(sum((xi - x_mean) ** 2 for xi in x))
    denominator_y = math.sqrt(sum((yi - y_mean) ** 2 for yi in y))

    if denominator_x == 0 or denominator_y == 0:
        return None

    return round(numerator / (denominator_x * denominator_y), 3)


def rank_values(values):
    sorted_values = sorted((value, index) for index, value in enumerate(values))
    ranks = [0] * len(values)

    i = 0
    while i < len(sorted_values):
        j = i
        while j < len(sorted_values) and sorted_values[j][0] == sorted_values[i][0]:
            j += 1

        average_rank = (i + j + 1) / 2

        for k in range(i, j):
            ranks[sorted_values[k][1]] = average_rank

        i = j

    return ranks


def comparative_percentiles(values, higher_is_better):
    """Return 0–100 within-study percentile ranks, preserving missing values."""
    available = [(index, value) for index, value in enumerate(values) if value is not None]
    scores = [None] * len(values)
    if len(available) < 3:
        return scores

    ordered_values = [(-value if higher_is_better else value) for _, value in available]
    ranks = rank_values(ordered_values)
    denominator = len(available) - 1
    for (index, _), rank in zip(available, ranks):
        scores[index] = round(100 * (len(available) - rank) / denominator, 2)
    return scores


def spearman_correlation(x_values, y_values):
    pairs = [
        (x, y) for x, y in zip(x_values, y_values)
        if x is not None and y is not None
    ]

    if len(pairs) < 2:
        return None

    x = [p[0] for p in pairs]
    y = [p[1] for p in pairs]

    return pearson_correlation(rank_values(x), rank_values(y))


def interpret_correlation(value):
    if value is None:
        return _("Correlation cannot be calculated")

    abs_value = abs(value)

    if abs_value >= 0.7:
        strength = _("strong")
    elif abs_value >= 0.4:
        strength = _("moderate")
    elif abs_value >= 0.2:
        strength = _("weak")
    else:
        strength = _("very weak")

    direction = _("positive") if value > 0 else _("negative")
    return _("%(direction)s %(strength)s correlation", direction=direction, strength=strength)


def correlation_record(x_values, y_values):
    pairs = [(x, y) for x, y in zip(x_values, y_values) if x is not None and y is not None]
    sample_size = len(pairs)
    pearson = pearson_correlation(x_values, y_values) if sample_size >= 3 else None
    spearman = spearman_correlation(x_values, y_values) if sample_size >= 3 else None
    return {
        "n": sample_size,
        "pearson": pearson,
        "spearman": spearman,
        "interpretation": interpret_correlation(spearman),
        "exploratory": sample_size < 10,
    }


def build_paired_analysis(results):
    """Build descriptive original/corrected comparisons from manifest metadata."""
    groups = {}
    condition_aliases = {
        "original": "original", "before": "original", "baseline": "original",
        "corrected": "corrected", "fixed": "corrected", "after": "corrected",
    }
    for item in results:
        pair_key = (item.get("pair_key") or "").strip()
        condition = condition_aliases.get((item.get("condition_label") or "").strip().casefold())
        if pair_key and condition and item.get("status") == "completed":
            groups.setdefault(pair_key, {}).setdefault(condition, []).append(item)

    pairs = []
    for pair_key in sorted(groups):
        group = groups[pair_key]
        if len(group.get("original", [])) != 1 or len(group.get("corrected", [])) != 1:
            continue
        original = group["original"][0]
        corrected = group["corrected"][0]
        axe_original = original.get("axe_violations")
        axe_corrected = corrected.get("axe_violations")
        lighthouse_original = original.get("lighthouse_score")
        lighthouse_corrected = corrected.get("lighthouse_score")
        pairs.append({
            "pair_key": pair_key,
            "original_result_id": original.get("id"),
            "corrected_result_id": corrected.get("id"),
            "stratum": original.get("stratum") or corrected.get("stratum"),
            "original_id": original.get("display_url") or original.get("url"),
            "corrected_id": corrected.get("display_url") or corrected.get("url"),
            "axe_original": axe_original,
            "axe_corrected": axe_corrected,
            "axe_reduction": (
                axe_original - axe_corrected
                if axe_original is not None and axe_corrected is not None else None
            ),
            "lighthouse_original": lighthouse_original,
            "lighthouse_corrected": lighthouse_corrected,
            "lighthouse_gain": (
                lighthouse_corrected - lighthouse_original
                if lighthouse_original is not None and lighthouse_corrected is not None else None
            ),
        })

    axe_reductions = [item["axe_reduction"] for item in pairs if item["axe_reduction"] is not None]
    lighthouse_gains = [item["lighthouse_gain"] for item in pairs if item["lighthouse_gain"] is not None]
    return {
        "available": bool(pairs),
        "complete_pairs": len(pairs),
        "candidate_pairs": len(groups),
        "pairs": pairs,
        "axe_mean_reduction": safe_mean(axe_reductions),
        "axe_median_reduction": safe_median(axe_reductions),
        "axe_improved": sum(value > 0 for value in axe_reductions),
        "axe_unchanged": sum(value == 0 for value in axe_reductions),
        "axe_worsened": sum(value < 0 for value in axe_reductions),
        "lighthouse_mean_gain": safe_mean(lighthouse_gains),
        "lighthouse_median_gain": safe_median(lighthouse_gains),
        "lighthouse_improved": sum(value > 0 for value in lighthouse_gains),
        "lighthouse_unchanged": sum(value == 0 for value in lighthouse_gains),
        "lighthouse_worsened": sum(value < 0 for value in lighthouse_gains),
    }


def build_experiment_analysis(results):
    results = [project_wcag(row) for row in results]
    valid_results = [item for item in results if item.get("status") == "completed"]
    total_urls = len(results)
    completed_urls = len(valid_results)
    axe_values = [item.get("axe_violations") for item in valid_results]
    axe_critical_values = [
        item.get("axe_critical") or 0
        if item.get("axe_violations") is not None else None
        for item in valid_results
    ]
    lighthouse_values = [item.get("lighthouse_score") for item in valid_results]
    dom_values = [item.get("dom_nodes") for item in valid_results]
    image_values = [item.get("images") for item in valid_results]
    execution_values = [item.get("execution_seconds") for item in valid_results]
    wave_errors_values = [
        item.get("wave_errors") if item.get("wave_status") == "completed" else None
        for item in valid_results
    ]
    wave_aim_values = [
        item.get("wave_aim_score") if item.get("wave_status") == "completed" else None
        for item in valid_results
    ]
    semantic_values = [
        len(item.get("semantic_findings") or [])
        if item.get("semantic_status") == "completed" else None
        for item in valid_results
    ]
    semantic_severity_values = {
        severity: [
            sum(
                1 for finding in (item.get("semantic_findings") or [])
                if finding.get("severity") == severity
            ) if item.get("semantic_status") == "completed" else None
            for item in valid_results
        ]
        for severity in ("high", "medium", "low")
    }
    semantic_severity_values["unknown"] = [
        sum(
            1 for finding in (item.get("semantic_findings") or [])
            if finding.get("severity") not in {"high", "medium", "low"}
        ) if item.get("semantic_status") == "completed" else None
        for item in valid_results
    ]
    axe_density_values = [
        round((axe or 0) * 1000 / dom, 2) if dom and axe is not None else None
        for axe, dom in zip(axe_values, dom_values)
    ]
    weighted_density_values = []
    for item in valid_results:
        dom = item.get("dom_nodes")
        weighted = (
            4 * (item.get("axe_critical") or 0)
            + 3 * (item.get("axe_serious") or 0)
            + 2 * (item.get("axe_moderate") or 0)
            + (item.get("axe_minor") or 0)
        )
        weighted_density_values.append(round(weighted * 1000 / dom, 2) if dom else None)

    complete_core_indices = [
        index for index, values in enumerate(zip(axe_values, lighthouse_values))
        if all(value is not None for value in values)
    ]
    ranking_includes_wave = bool(complete_core_indices) and all(
        wave_aim_values[index] is not None for index in complete_core_indices
    )
    composite_axe = [None] * completed_urls
    composite_lighthouse = [None] * completed_urls
    composite_wave_aim = [None] * completed_urls
    composite_scores = [None] * completed_urls
    composite_disagreement = [None] * completed_urls

    if len(complete_core_indices) >= 3:
        complete_axe = [axe_values[index] for index in complete_core_indices]
        complete_lighthouse = [lighthouse_values[index] for index in complete_core_indices]
        axe_percentiles = comparative_percentiles(complete_axe, higher_is_better=False)
        lighthouse_percentiles = comparative_percentiles(complete_lighthouse, higher_is_better=True)
        aim_percentiles = None
        if ranking_includes_wave:
            complete_aim = [wave_aim_values[index] for index in complete_core_indices]
            aim_percentiles = comparative_percentiles(complete_aim, higher_is_better=True)

        for position, index in enumerate(complete_core_indices):
            components = [
                axe_percentiles[position],
                lighthouse_percentiles[position],
            ]
            composite_axe[index], composite_lighthouse[index] = components
            if aim_percentiles is not None:
                composite_wave_aim[index] = aim_percentiles[position]
                components.append(aim_percentiles[position])
            composite_scores[index] = round(mean(components), 2)
            composite_disagreement[index] = round(max(components) - min(components), 2)

    total_axe = sum(value for value in axe_values if value is not None)
    total_critical = sum(item.get("axe_critical") or 0 for item in valid_results)
    total_serious = sum(item.get("axe_serious") or 0 for item in valid_results)
    total_moderate = sum(item.get("axe_moderate") or 0 for item in valid_results)
    total_minor = sum(item.get("axe_minor") or 0 for item in valid_results)

    total_semantic_findings = sum(value for value in semantic_values if value is not None)
    total_wave_errors = sum(value for value in wave_errors_values if value is not None)
    total_wave_credits = sum(item.get("wave_credits_used") or 0 for item in valid_results)
    total_wave_cost = round(sum(
        float(item.get("wave_cost_usd") or 0)
        for item in valid_results if (item.get("provenance") or "fresh") == "fresh"
    ), 6)
    total_llm_tokens = sum(item.get("semantic_total_tokens") or 0 for item in valid_results)
    total_llm_cost = round(sum(
        float(item.get("semantic_cost_usd") or 0)
        for item in valid_results if (item.get("provenance") or "fresh") == "fresh"
    ), 6)

    correlations = {
        "axe_lighthouse": {
            **correlation_record(axe_values, lighthouse_values),
        },
        "axe_critical_lighthouse": correlation_record(
            axe_critical_values, lighthouse_values
        ),
        "axe_density_lighthouse": correlation_record(axe_density_values, lighthouse_values),
        "dom_axe": correlation_record(dom_values, axe_values),
        "dom_axe_density": correlation_record(dom_values, axe_density_values),
        "images_axe": correlation_record(image_values, axe_values),
        "semantic_axe": correlation_record(semantic_values, axe_values),
        "wave_axe": correlation_record(wave_errors_values, axe_values),
        "wave_lighthouse": correlation_record(wave_errors_values, lighthouse_values),
        "wave_aim_lighthouse": correlation_record(wave_aim_values, lighthouse_values),
        "wave_aim_axe_density": correlation_record(wave_aim_values, axe_density_values),
        "wave_aim_axe": correlation_record(wave_aim_values, axe_values),
        "time_dom": correlation_record(execution_values, dom_values),
    }

    semantic_category_counts = {}

    wave_category_totals = {
        "errors": sum(item.get("wave_errors") or 0 for item in valid_results if item.get("wave_status") == "completed"),
        "contrast": sum(item.get("wave_contrast_errors") or 0 for item in valid_results if item.get("wave_status") == "completed"),
        "alerts": sum(item.get("wave_alerts") or 0 for item in valid_results if item.get("wave_status") == "completed"),
        "features": sum(item.get("wave_features") or 0 for item in valid_results if item.get("wave_status") == "completed"),
        "structure": sum(item.get("wave_structure") or 0 for item in valid_results if item.get("wave_status") == "completed"),
        "aria": sum(item.get("wave_aria") or 0 for item in valid_results if item.get("wave_status") == "completed"),
    }

    for item in valid_results:
        for finding in item.get("semantic_findings", []):
            category = finding.get("category")
            if category:
                semantic_category_counts[category] = semantic_category_counts.get(category, 0) + 1

    top_semantic_categories = sorted(
        semantic_category_counts.items(),
        key=lambda item: item[1],
        reverse=True
    )[:3]

    ranked_pages = sorted(
        [
            {
                "result_id": item.get("id"),
                "url": item.get("url"),
                "display_name": item.get("display_url") or item.get("url"),
                "is_local_html": bool(item.get("dataset_observation_id")),
                "axe_issues": item.get("axe_violations"),
                "axe_density": density,
                "weighted_density": weighted,
                "composite_score": composite_scores[index],
                "tool_disagreement": composite_disagreement[index],
                "composite_components": {
                    "axe": composite_axe[index],
                    "lighthouse": composite_lighthouse[index],
                    "wave_aim": composite_wave_aim[index],
                },
                "lighthouse": item.get("lighthouse_score"),
                "wave_aim": item.get("wave_aim_score") if item.get("wave_status") == "completed" else None,
                "screenshot_path": item.get("screenshot_path"),
                "screenshot_mode": item.get("screenshot_mode"),
                "sensitive_preview": item.get("site_category") == "Adult Content",
            }
            for index, (item, density, weighted) in enumerate(zip(valid_results, axe_density_values, weighted_density_values))
            if item.get("axe_violations") is not None
        ],
        key=lambda item: (
            item["composite_score"] is not None,
            item["composite_score"] if item["composite_score"] is not None else -1,
            item["axe_issues"] if item["axe_issues"] is not None else -1,
        ),
        reverse=True,
    )
    derived_by_id = {
        page["result_id"]: page for page in ranked_pages
    }
    measurement_rows = []
    for item in results:
        findings = item.get("semantic_findings") or []
        derived = derived_by_id.get(item.get("id"), {})
        measurement_rows.append({
            **item,
            "axe_density": derived.get("axe_density"),
            "weighted_density": derived.get("weighted_density"),
            "semantic_findings_count": len(findings) if item.get("semantic_status") == "completed" else None,
            "semantic_high_count": sum(1 for finding in findings if finding.get("severity") == "high"),
            "semantic_medium_count": sum(1 for finding in findings if finding.get("severity") == "medium"),
            "semantic_low_count": sum(1 for finding in findings if finding.get("severity") == "low"),
        })
    composite_coverage = sum(value is not None for value in composite_scores)

    def quartiles(values):
        ordered = sorted(float(value) for value in values if value is not None)
        if not ordered:
            return {"q1": None, "median": None, "q3": None, "whisker_low": None, "whisker_high": None, "outliers": []}
        def percentile(position):
            index = (len(ordered) - 1) * position
            lower = int(index)
            upper = min(lower + 1, len(ordered) - 1)
            return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower), 2)
        q1, middle, q3 = percentile(.25), percentile(.5), percentile(.75)
        spread = q3 - q1
        lower_fence, upper_fence = q1 - 1.5 * spread, q3 + 1.5 * spread
        within_fences = [value for value in ordered if lower_fence <= value <= upper_fence]
        return {
            "q1": q1, "median": middle, "q3": q3,
            "whisker_low": within_fences[0], "whisker_high": within_fences[-1],
            "outliers": [value for value in ordered if value < lower_fence or value > upper_fence],
        }

    def axe_rule_counts(item):
        path = item.get("axe_raw_path")
        if not path:
            return {}
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            return {
                entry.get("id"): len(entry.get("nodes", []))
                for entry in payload.get("violations", []) if entry.get("id")
            }
        except (OSError, ValueError, TypeError):
            return {}

    webaim_rule_map = {
        # This crosswalk intentionally follows WAVE error items, not every Axe
        # rule associated with the same WCAG success criterion. WAVE reports
        # missing select labels as an alert, for example, so select-name is not
        # part of the WebAIM Million "missing form labels" proxy below.
        "Low contrast": {"color-contrast"},
        "Missing alternative text": {"image-alt", "input-image-alt", "area-alt"},
        "Missing form labels": {"label"},
        "Empty links": {"link-name"},
        "Empty buttons": {"button-name", "input-button-name"},
        "Missing document language": {"html-has-lang", "html-lang-valid"},
    }
    rule_counts_by_result = {item.get("id"): axe_rule_counts(item) for item in valid_results}
    rule_ids_by_result = {
        result_id: set(counts) for result_id, counts in rule_counts_by_result.items()
    }
    rule_sets = list(rule_ids_by_result.values())
    def design_weight(item):
        frame = float(item.get("tranco_frame_count") or 0)
        selected = float(item.get("tranco_selected_count") or 0)
        return frame / selected if frame and selected else 1.0

    total_design_weight = sum(design_weight(item) for item in valid_results)

    def weighted_mean(field):
        pairs = [(float(item[field]), design_weight(item)) for item in valid_results if item.get(field) is not None]
        return round(sum(value * weight for value, weight in pairs) / sum(weight for _value, weight in pairs), 2) if pairs else None

    def weighted_percent(predicate):
        return round(100 * sum(design_weight(item) for item in valid_results if predicate(item)) / total_design_weight, 1) if total_design_weight else 0

    def observed_percent(predicate):
        return round(100 * sum(1 for item in valid_results if predicate(item)) / len(valid_results), 1) if valid_results else 0

    webaim_common_errors = [
        {
            "name": name,
            "pages": sum(bool(rule_ids & ids) for rule_ids in rule_sets),
            "percent": weighted_percent(lambda item, ids=ids: bool(rule_ids_by_result.get(item.get("id"), set()) & ids)),
        }
        for name, ids in webaim_rule_map.items()
    ]
    six_common_rules = set().union(*webaim_rule_map.values())
    weighted_six_common_issues = sum(
        sum(rule_counts_by_result.get(item.get("id"), {}).get(rule, 0) for rule in six_common_rules)
        * design_weight(item)
        for item in valid_results
    )
    weighted_all_issues = sum(
        (item.get("axe_violations") or 0) * design_weight(item)
        for item in valid_results
    )
    observed_six_common_issues = sum(
        sum(rule_counts_by_result.get(item.get("id"), {}).get(rule, 0) for rule in six_common_rules)
        for item in valid_results
    )
    observed_all_issues = sum(item.get("axe_violations") or 0 for item in valid_results)
    webaim_2026_common_error_rates = [83.9, 53.1, 51.0, 46.3, 30.6, 13.5]
    warp_common_error_rates = [row["percent"] for row in webaim_common_errors]
    webaim_pattern_benchmark = {
        "categories": len(webaim_common_errors),
        "pearson": pearson_correlation(warp_common_error_rates, webaim_2026_common_error_rates),
        "spearman": spearman_correlation(warp_common_error_rates, webaim_2026_common_error_rates),
        "mean_absolute_gap": round(mean(abs(warp - wave) for warp, wave in zip(
            warp_common_error_rates, webaim_2026_common_error_rates
        )), 1),
    }

    minimum_research_group_size = max(5, ceil(len(valid_results) * .005))

    def grouped_research_rows(key, missing_label, minimum_size=minimum_research_group_size):
        groups = {}
        for item in valid_results:
            label = str(item.get(key) or "").strip() or missing_label
            groups.setdefault(label, []).append(item)
        overall = weighted_mean("axe_violations") or 0
        def group_mean(items):
            pairs = [(float(item.get("axe_violations") or 0), design_weight(item)) for item in items]
            return round(sum(value * weight for value, weight in pairs) / sum(weight for _value, weight in pairs), 2) if pairs else None
        rows = [{
            "name": name,
            "pages": len(items),
            "estimated_pages": round(sum(design_weight(item) for item in items)),
            "axe_mean": group_mean(items),
            "difference_percent": round(100 * ((group_mean(items) or 0) - overall) / overall, 1) if overall else None,
        } for name, items in groups.items() if len(items) >= minimum_size]
        return sorted(rows, key=lambda row: (
            row["difference_percent"] is None,
            row["difference_percent"] if row["difference_percent"] is not None else float("inf"),
            -row["pages"],
            row["name"],
        ))

    for item in valid_results:
        hostname = (urlsplit(item.get("captured_url") or item.get("url") or "").hostname or "").lower()
        item["_research_tld"] = hostname.rsplit(".", 1)[-1] if "." in hostname else "Undeclared"

    def base_language(code):
        normalized = str(code or "").strip().replace("_", "-")
        if not normalized:
            return "Undeclared"
        base = normalized.split("-", 1)[0].lower()
        return {"iw": "he", "in": "id", "ji": "yi"}.get(base, base)

    def humanize_language_rows(rows):
        for row in rows:
            code = row["name"]
            row["code"] = None if code == "Undeclared" else code
            if row["code"] is None:
                row["display_name"] = "No language specified"
                row["name"] = row["display_name"]
                continue
            try:
                display_name = Locale.parse(code.replace("_", "-"), sep="-").get_display_name("en")
            except (UnknownLocaleError, ValueError):
                display_name = None
            row["display_name"] = display_name.title() if display_name else code
            row["name"] = row["display_name"]
        return rows

    for item in valid_results:
        item["_research_language"] = base_language(item.get("language_declared"))

    completed_count = len(valid_results)
    weighted_image_total = sum((item.get("images") or 0) * design_weight(item) for item in valid_results)
    weighted_missing_alt_total = sum((item.get("images_without_alt") or 0) * design_weight(item) for item in valid_results)
    structure_benchmark = {
        "images_mean": weighted_mean("images"),
        "images_without_alt_mean": weighted_mean("images_without_alt"),
        "images_missing_alt_percent": round(100 * weighted_missing_alt_total / weighted_image_total, 1) if weighted_image_total else 0,
        "inputs_mean": weighted_mean("inputs"),
        "headings_mean": weighted_mean("headings"),
        "pages_without_headings_percent": weighted_percent(lambda item: (item.get("headings") or 0) == 0),
        "pages_multiple_h1_percent": weighted_percent(lambda item: (item.get("h1_count") or 0) > 1),
        "main_landmark_percent": weighted_percent(lambda item: bool(item.get("has_main_landmark"))),
        "any_landmark_percent": weighted_percent(lambda item: any(bool(item.get(field)) for field in (
            "has_main_landmark", "has_nav_landmark", "has_header_landmark", "has_footer_landmark"
        ))),
    }
    webaim_tld_error_means = {
        "gov": 18.5, "edu": 23.0, "us": 30.5, "xyz": 31.9, "io": 34.9,
        "ca": 36.0, "uk": 40.9, "org": 44.2, "nl": 45.5, "de": 46.3,
        "co": 49.8, "fr": 53.3, "net": 53.3, "com": 56.2, "au": 56.6,
        "eu": 57.0, "es": 57.0, "jp": 57.3, "in": 58.3, "it": 59.5,
        "br": 62.5, "pl": 67.1, "cz": 73.2, "ru": 75.4, "vn": 78.6,
        "cn": 82.6, "ua": 103.1,
    }
    tld_rows = grouped_research_rows("_research_tld", "Undeclared")
    for row in tld_rows:
        row["webaim_mean"] = webaim_tld_error_means.get(row["name"])
    comparable_tld_rows = [row for row in tld_rows if row["webaim_mean"] is not None]
    stable_tld_rows = [row for row in comparable_tld_rows if row["pages"] >= 10]
    tld_pattern_benchmark = {
        "groups": len(stable_tld_rows),
        "pearson": pearson_correlation(
            [row["axe_mean"] for row in stable_tld_rows],
            [row["webaim_mean"] for row in stable_tld_rows],
        ),
        "spearman": spearman_correlation(
            [row["axe_mean"] for row in stable_tld_rows],
            [row["webaim_mean"] for row in stable_tld_rows],
        ),
    }
    webaim_comparison = {
        "pages": completed_count,
        "minimum_research_group_size": minimum_research_group_size,
        "axe_mean": weighted_mean("axe_violations"),
        "dom_mean": round(weighted_mean("dom_nodes") or 0),
        "elements_per_issue": round(
            sum((item.get("dom_nodes") or 0) * design_weight(item) for item in valid_results)
            / sum((item.get("axe_violations") or 0) * design_weight(item) for item in valid_results), 1
        ) if sum((item.get("axe_violations") or 0) * design_weight(item) for item in valid_results) else None,
        "pages_with_wcag_failures_percent": weighted_percent(lambda item: (item.get("axe_wcag_violations") or 0) > 0),
        "observed_pages_with_wcag_failures_percent": observed_percent(lambda item: (item.get("axe_wcag_violations") or 0) > 0),
        "pages_with_five_or_fewer_percent": weighted_percent(lambda item: (item.get("axe_violations") or 0) <= 5),
        "observed_pages_with_five_or_fewer_percent": observed_percent(lambda item: (item.get("axe_violations") or 0) <= 5),
        "pages_with_ten_or_fewer_percent": weighted_percent(lambda item: (item.get("axe_violations") or 0) <= 10),
        "observed_pages_with_ten_or_fewer_percent": observed_percent(lambda item: (item.get("axe_violations") or 0) <= 10),
        "six_common_error_share_percent": round(100 * weighted_six_common_issues / weighted_all_issues, 1) if weighted_all_issues else 0,
        "observed_six_common_error_share_percent": round(100 * observed_six_common_issues / observed_all_issues, 1) if observed_all_issues else 0,
        "ambiguous_link_pages_percent": weighted_percent(lambda item: (item.get("ambiguous_links") or 0) > 0),
        "observed_ambiguous_link_pages_percent": observed_percent(lambda item: (item.get("ambiguous_links") or 0) > 0),
        "ambiguous_links_affected_mean": round(
            sum((item.get("ambiguous_links") or 0) * design_weight(item) for item in valid_results if (item.get("ambiguous_links") or 0) > 0)
            / sum(design_weight(item) for item in valid_results if (item.get("ambiguous_links") or 0) > 0), 1
        ) if any((item.get("ambiguous_links") or 0) > 0 for item in valid_results) else 0,
        "common_errors": webaim_common_errors,
        "pattern_benchmark": webaim_pattern_benchmark,
        "structure": structure_benchmark,
        "tlds": comparable_tld_rows,
        "tld_pattern_benchmark": tld_pattern_benchmark,
        "aria_attributes_mean": weighted_mean("aria_attributes"),
        "aria_pages_percent": weighted_percent(lambda item: bool(item.get("uses_aria"))),
        "skip_link_pages_percent": weighted_percent(lambda item: (item.get("skip_links") or 0) > 0),
        "broken_skip_links_percent": round(100 * sum(item.get("broken_skip_links") or 0 for item in valid_results) / sum(item.get("skip_links") or 0 for item in valid_results), 1) if sum(item.get("skip_links") or 0 for item in valid_results) else 0,
        "html5_doctype_percent": weighted_percent(lambda item: bool(item.get("valid_html5_doctype"))),
        "languages": humanize_language_rows(grouped_research_rows("_research_language", "Undeclared")),
        "categories": grouped_research_rows("site_category", "Unclassified"),
        "category_sources": sorted({
            str(item.get("site_category_source") or "").strip()
            for item in valid_results if item.get("site_category") and item.get("site_category_source")
        }),
    }

    tranco_groups = {}
    for item in valid_results:
        group = item.get("tranco_stratum")
        if group:
            tranco_groups.setdefault(group, []).append(item)
    tranco_strata = []
    tranco_axe_total = sum(
        float(item.get("axe_violations") or 0)
        for items in tranco_groups.values() for item in items
    )
    for group, items in tranco_groups.items():
        axe = [item.get("axe_violations") for item in items if item.get("axe_violations") is not None]
        critical = [item.get("axe_critical") for item in items if item.get("axe_critical") is not None]
        lighthouse = [item.get("lighthouse_score") for item in items if item.get("lighthouse_score") is not None]
        wave_aim = [item.get("wave_aim_score") for item in items if item.get("wave_aim_score") is not None]
        llm_high = [
            sum(1 for finding in (item.get("semantic_findings") or []) if finding.get("severity") == "high")
            for item in items if item.get("semantic_status") == "completed"
        ]
        tranco_strata.append({
            "name": group,
            "n": len(items),
            "zero_critical_percent": round(100 * sum((value or 0) == 0 for value in critical) / len(critical), 1) if critical else 0,
            "lighthouse_90_percent": round(100 * sum((value or 0) >= 90 for value in lighthouse) / len(lighthouse), 1) if lighthouse else 0,
            "axe_issue_share_percent": round(100 * sum(axe) / tranco_axe_total, 1) if tranco_axe_total else 0,
            "axe_mean": safe_mean(axe),
            "lighthouse_mean": safe_mean(lighthouse),
            "axe": quartiles(axe),
            "critical": quartiles(critical),
            "lighthouse": quartiles(lighthouse),
            "wave_aim": quartiles(wave_aim),
            "llm_high": quartiles(llm_high),
        })

    return {
        "paired": build_paired_analysis(results),
        "general": {
            "total_urls": total_urls,
            "completed_urls": completed_urls,
            "failed_urls": total_urls - completed_urls,
            "total_axe": total_axe,
            "total_semantic_findings": total_semantic_findings,
            "total_wave_errors": total_wave_errors,
            "total_wave_credits": total_wave_credits,
            "total_wave_cost": total_wave_cost,
            "total_llm_tokens": total_llm_tokens,
            "total_llm_cost": total_llm_cost,
            "total_api_cost": round(total_wave_cost + total_llm_cost, 6),
            "wave_aim_mean": safe_mean(wave_aim_values),
            "lighthouse_mean": safe_mean(lighthouse_values),
            "lighthouse_median": safe_median(lighthouse_values),
            "axe_density_mean": safe_mean(axe_density_values),
            "weighted_density_mean": safe_mean(weighted_density_values),
            "dom_mean": safe_mean(dom_values),
            "execution_mean": safe_mean(execution_values),
            "execution_stdev": safe_stdev(execution_values),
            "reused_results": sum(
                item.get("provenance") in {"cache", "composed", "imported"}
                for item in valid_results
            ),
        },
        "coverage": {
            "axe": sum(value is not None for value in axe_values),
            "lighthouse": sum(value is not None for value in lighthouse_values),
            "wave": sum(value is not None for value in wave_errors_values),
            "composite": composite_coverage,
            "semantic": sum(value is not None for value in semantic_values),
        },
        "severity": {
            "critical": total_critical,
            "serious": total_serious,
            "moderate": total_moderate,
            "minor": total_minor,
        },
        "correlations": correlations,
        "top_semantic_categories": top_semantic_categories,
        "wave_categories": wave_category_totals,
        "tranco_strata": tranco_strata,
        "webaim_comparison": webaim_comparison,
        "ranked_pages": ranked_pages,
        "measurement_rows": measurement_rows,
        "measurement_extras": [
            {
                "evaluated_at": str(item.get("evaluated_at") or item.get("created_at") or ""),
                "provenance": item.get("provenance") or "fresh",
                "source_experiment": item.get("source_experiment_id"),
                "dom": item.get("dom_nodes"),
                "images": item.get("images"),
                "links": item.get("links"),
                "headings": item.get("headings"),
                "runtime": round(item.get("execution_seconds"), 2) if item.get("execution_seconds") is not None else None,
                "axe_best_practice": item.get("axe_best_practice_issues"),
                "wave_credits": item.get("wave_credits_used"),
                "wave_cost": float(item["wave_cost_usd"]) if item.get("wave_cost_usd") is not None else None,
                "llm_tokens": item.get("semantic_total_tokens"),
                "llm_cost": float(item["semantic_cost_usd"]) if item.get("semantic_cost_usd") is not None else None,
                "total_cost": round(
                    float(item.get("wave_cost_usd") or 0)
                    + float(item.get("semantic_cost_usd") or 0),
                    6,
                ),
                "tranco_rank": item.get("tranco_rank"),
                "tranco_stratum": item.get("tranco_stratum"),
                "site_category": item.get("site_category") or _("Unclassified"),
                "tranco_stratum_order": {
                    "rank_1_500": 1, "Global top 500": 1,
                    "rank_501_5000": 2, "Very high popularity": 2,
                    "rank_5001_50000": 3, "High popularity": 3,
                    "rank_50001_250000": 4, "Medium popularity": 4,
                    "rank_250001_1000000": 5, "Popularity tail": 5,
                }.get(item.get("tranco_stratum")),
            }
            for item in results
        ],
        "ranking_mode": "composite" if composite_coverage >= 3 else "unavailable",
        "ranking_includes_wave": ranking_includes_wave and composite_coverage >= 3,
        "ranking_tool_count": 3 if ranking_includes_wave and composite_coverage >= 3 else 2,
        "chart": {
            # Every visible report label must use the page's single global name.
            # The technical URL remains available on the result for navigation and exports.
            "labels": [item.get("display_url") or item.get("display_name") or item.get("url") for item in valid_results],
            "axe": axe_values,
            "axe_critical_only": axe_critical_values,
            "axe_density": axe_density_values,
            "weighted_density": weighted_density_values,
            "composite_score": composite_scores,
            "tool_disagreement": composite_disagreement,
            "lighthouse": lighthouse_values,
            "dom": dom_values,
            "execution": execution_values,
            "critical": [item.get("axe_critical") or 0 for item in valid_results],
            "serious": [item.get("axe_serious") or 0 for item in valid_results],
            "moderate": [item.get("axe_moderate") or 0 for item in valid_results],
            "minor": [item.get("axe_minor") or 0 for item in valid_results],
            "wave_errors": [item.get("wave_errors") if item.get("wave_status") == "completed" else None for item in valid_results],
            "wave_contrast": [item.get("wave_contrast_errors") if item.get("wave_status") == "completed" else None for item in valid_results],
            "wave_alerts": [item.get("wave_alerts") if item.get("wave_status") == "completed" else None for item in valid_results],
            "wave_features": [item.get("wave_features") if item.get("wave_status") == "completed" else None for item in valid_results],
            "wave_structure": [item.get("wave_structure") if item.get("wave_status") == "completed" else None for item in valid_results],
            "wave_aria": [item.get("wave_aria") if item.get("wave_status") == "completed" else None for item in valid_results],
            "wave_aim": wave_aim_values,
            "semantic_high": semantic_severity_values["high"],
            "semantic_medium": semantic_severity_values["medium"],
            "semantic_low": semantic_severity_values["low"],
            "semantic_unknown": semantic_severity_values["unknown"],
        },
    }

@experiments_bp.route("/experiments/<int:experiment_id>/loading", methods=["GET"])
def experiment_report_loading(experiment_id):
    """Show a lightweight report page before assembling large result sets."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id, title FROM experiments WHERE id = %s",
            (experiment_id,),
        )
        experiment = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()
    if not experiment:
        flash(_("The requested evaluation experiment does not exist."), "danger")
        return redirect(url_for("experiments.experiments"))
    return render_template("report_transition.html", experiment=experiment)


@experiments_bp.route("/experiments/<int:experiment_id>", methods=["GET"])
def experiment_report(experiment_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, title, urls, include_semantic, include_wave, semantic_provider,
               semantic_model, axe_standard, axe_include_best_practices,
               reuse_cached_results, experiment_origin,
               source_type, dataset_id, resource_policy,
               status, created_at, completed_at
        FROM experiments
        WHERE id = %s
    """, (experiment_id,))
    experiment = cursor.fetchone()

    if not experiment:
        cursor.close()
        conn.close()
        flash(_("The requested evaluation experiment does not exist."), "danger")
        return redirect(url_for("experiments.experiments"))

    cursor.execute("""
        SELECT r.*, COALESCE(r.display_name, o.display_name, o.observation_key, r.url) AS display_url,
               o.relative_path, o.pair_key, o.condition_label, o.stratum,
               o.expected_label
        FROM experiment_results r
        LEFT JOIN dataset_observations o ON o.id = r.dataset_observation_id
        WHERE r.experiment_id = %s
        ORDER BY r.id ASC
    """, (experiment_id,))
    results = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM experiment_environment
        WHERE experiment_id = %s
        ORDER BY id DESC
        LIMIT 1
    """, (experiment_id,))
    environment = cursor.fetchone()
    cursor.execute(
        "SELECT COUNT(*) AS total FROM experiment_environment WHERE experiment_id = %s",
        (experiment_id,),
    )
    environment_count = int((cursor.fetchone() or {}).get("total") or 0)
    if not environment:
        cursor.execute(
            """
            SELECT ee.*
            FROM experiment_results r
            JOIN experiment_environment ee
              ON ee.experiment_id = COALESCE(r.source_experiment_id, r.experiment_id)
            WHERE r.experiment_id = %s
            ORDER BY ee.id DESC
            LIMIT 1
            """,
            (experiment_id,),
        )
        environment = cursor.fetchone()
        cursor.execute(
            """
            SELECT COUNT(DISTINCT ee.experiment_id) AS total
            FROM experiment_results r
            JOIN experiment_environment ee
              ON ee.experiment_id = COALESCE(r.source_experiment_id, r.experiment_id)
            WHERE r.experiment_id = %s
            """,
            (experiment_id,),
        )
        environment_count = int((cursor.fetchone() or {}).get("total") or 0)

    tranco_sample = None
    tranco_quality = None
    tranco_recovery = False
    tranco_active_stratum = None
    pending = experiment["status"] in {"queued", "running"}
    if experiment.get("source_type") == "tranco":
        cursor.execute("SELECT * FROM tranco_samples WHERE experiment_id=%s", (experiment_id,))
        tranco_sample = cursor.fetchone()
        if tranco_sample:
            for key in ("strata", "candidates"):
                if isinstance(tranco_sample.get(key), str):
                    tranco_sample[key] = json.loads(tranco_sample[key])
            tranco_recovery = any(
                int(candidate.get("retry_count") or 0) > 0
                or candidate.get("role") in {"excluded_failed", "selected_replacement"}
                for candidate in tranco_sample.get("candidates") or []
            )
            if pending:
                stored_urls = {item["url"] for item in results}
                pending_url = next(
                    (url.strip() for url in experiment["urls"].splitlines()
                     if url.strip() and url.strip() not in stored_urls),
                    None,
                )
                active_candidate = next(
                    (candidate for candidate in tranco_sample.get("candidates") or []
                     if candidate.get("url") == pending_url),
                    None,
                )
                if active_candidate:
                    tranco_active_stratum = (
                        active_candidate.get("stratum_name")
                        or active_candidate.get("stratum")
                    )
            active_roles = {"selected", "selected_replacement"}
            selected_by_url = {
                normalize_url(candidate["url"]): candidate
                for candidate in tranco_sample.get("candidates") or []
                if candidate.get("role") in active_roles
            }
            results_by_url = {
                normalize_url(item.get("url")): item for item in results
            }
            stratum_design = {
                stratum.get("label"): stratum
                for stratum in tranco_sample.get("strata") or []
            }
            for item in results:
                candidate = selected_by_url.get(normalize_url(item.get("url"))) or {}
                design = stratum_design.get(candidate.get("stratum")) or {}
                item["tranco_rank"] = candidate.get("rank")
                item["tranco_stratum"] = candidate.get("stratum_name") or candidate.get("stratum")
                item["tranco_frame_count"] = design.get("frame_count")
                item["tranco_selected_count"] = design.get("selected_count")
            strata_quality = []
            for stratum in tranco_sample.get("strata") or []:
                if int(stratum.get("selected_count") or 0) == 0:
                    continue
                stratum_candidates = [
                    candidate for candidate in tranco_sample.get("candidates") or []
                    if candidate.get("stratum") == stratum.get("label")
                ]
                active = [
                    candidate for candidate in stratum_candidates
                    if candidate.get("role") in active_roles
                ]
                completed = sum(
                    results_by_url.get(normalize_url(candidate.get("url")), {}).get("status") == "completed"
                    for candidate in active
                )
                failed = sum(
                    results_by_url.get(normalize_url(candidate.get("url")), {}).get("status") == "failed"
                    for candidate in active
                )
                excluded = sum(
                    candidate.get("role") == "excluded_failed"
                    for candidate in stratum_candidates
                )
                controlled_retries = sum(
                    int(candidate.get("retry_count") or 0)
                    for candidate in stratum_candidates
                )
                replacement_completed = sum(
                    candidate.get("role") == "selected_replacement"
                    and results_by_url.get(
                        normalize_url(candidate.get("url")), {}
                    ).get("status") == "completed"
                    for candidate in stratum_candidates
                )
                strata_quality.append({
                    **stratum,
                    "completed": completed,
                    "domains_evaluated": completed + excluded + failed,
                    "excluded": excluded,
                    "controlled_retries": controlled_retries,
                    "replacement_share": round(
                        100 * replacement_completed / completed, 1
                    ) if completed else 0,
                })
            failed_urls = {
                item.get("url") for item in results if item.get("status") == "failed"
            }
            retryable = sum(
                candidate.get("role") in active_roles
                and candidate.get("url") in failed_urls
                and int(candidate.get("retry_count") or 0) < 1
                for candidate in tranco_sample.get("candidates") or []
            )
            tranco_quality = {
                "strata": strata_quality,
                "retryable": retryable,
                "replaceable": len(plan_failed_replacements(
                    tranco_sample.get("candidates") or [], failed_urls
                )),
                "excluded": sum(
                    candidate.get("role") == "excluded_failed"
                    for candidate in tranco_sample.get("candidates") or []
                ),
                "target_size": sum(
                    int(stratum.get("selected_count") or 0)
                    for stratum in tranco_sample.get("strata") or []
                ),
                "initial_excluded": sum(
                    candidate.get("role") == "excluded_failed" and not candidate.get("replaces")
                    for candidate in tranco_sample.get("candidates") or []
                ),
                "reserve_failures": sum(
                    candidate.get("role") == "excluded_failed" and bool(candidate.get("replaces"))
                    for candidate in tranco_sample.get("candidates") or []
                ),
                "replacements_used": sum(
                    bool(candidate.get("replaces"))
                    for candidate in tranco_sample.get("candidates") or []
                ),
                "controlled_retries": sum(
                    int(candidate.get("retry_count") or 0)
                    for candidate in tranco_sample.get("candidates") or []
                ),
            }
            population_size = sum(int(stratum.get("frame_count") or 0) for stratum in strata_quality)
            if target_size := sum(int(stratum.get("selected_count") or 0) for stratum in strata_quality):
                finite_correction = math.sqrt((population_size - target_size) / (population_size - 1)) if population_size > 1 else 1
                tranco_quality["worst_case_margin_95"] = round(100 * 1.96 * math.sqrt(.25 / target_size) * finite_correction, 2)
            else:
                tranco_quality["worst_case_margin_95"] = None
            tranco_quality["population_size"] = population_size
            active_failed = sum(
                candidate.get("role") in active_roles
                and candidate.get("url") in failed_urls
                for candidate in tranco_sample.get("candidates") or []
            )
            tranco_quality["reserve_exhausted"] = max(
                0,
                active_failed
                - tranco_quality["retryable"]
                - tranco_quality["replaceable"],
            )
            target_size = tranco_quality["target_size"]
            initial_failures = sum(
                not candidate.get("replaces")
                and (candidate.get("role") == "excluded_failed" or (
                    candidate.get("role") == "selected"
                    and results_by_url.get(normalize_url(candidate.get("url")), {}).get("status") == "failed"
                ))
                for candidate in tranco_sample.get("candidates") or []
            )
            tranco_quality["initial_yield_percent"] = round(
                100 * (target_size - initial_failures) / target_size, 1
            ) if target_size else None
            if sum(item["completed"] for item in strata_quality) < target_size:
                # A requested census with nonresponse must not display a
                # zero sampling margin as though every domain was observed.
                tranco_quality["worst_case_margin_95"] = None

    for item in results:
        findings = item.get("semantic_findings")
        if isinstance(findings, str):
            try:
                item["semantic_findings"] = json.loads(findings)
            except Exception:
                item["semantic_findings"] = []
        elif findings is None:
            item["semantic_findings"] = []
        acquisition_signals = item.get("acquisition_signals")
        if isinstance(acquisition_signals, str):
            try:
                item["acquisition_signals"] = json.loads(acquisition_signals)
            except Exception:
                item["acquisition_signals"] = []
        elif acquisition_signals is None:
            item["acquisition_signals"] = []

    cursor.close()
    conn.close()

    report_settings = get_settings()
    show_axe_best_practices = as_bool(experiment.get("axe_include_best_practices"))
    results = [project_wcag(row) for row in results]
    experiment["axe_include_best_practices"] = show_axe_best_practices

    chart_labels = [item.get("display_url") or item["url"] for item in results]
    axe_values = [item["axe_violations"] or 0 for item in results]
    lighthouse_values = [item["lighthouse_score"] or 0 for item in results]

    severity_totals = {
        "critical": sum(item["axe_critical"] or 0 for item in results),
        "serious": sum(item["axe_serious"] or 0 for item in results),
        "moderate": sum(item["axe_moderate"] or 0 for item in results),
        "minor": sum(item["axe_minor"] or 0 for item in results),
    }

    semantic_counts = {
        "low": sum(1 for item in results if item.get("semantic_risk_level") == "low"),
        "medium": sum(1 for item in results if item.get("semantic_risk_level") == "medium"),
        "high": sum(1 for item in results if item.get("semantic_risk_level") == "high"),
    }

    semantic_category_counts = {}

    for item in results:
        for finding in item.get("semantic_findings", []):
            category = finding.get("category", "unknown")
            semantic_category_counts[category] = semantic_category_counts.get(category, 0) + 1

    semantic_category_labels = list(semantic_category_counts.keys())
    semantic_category_values = list(semantic_category_counts.values())

    execution_values = [round(item["execution_seconds"] or 0, 2) for item in results]
    image_values = [item["images"] or 0 for item in results]
    dom_values = [item["dom_nodes"] or 0 for item in results]

    dom_values = [item["dom_nodes"] or 0 for item in results]
    image_values = [item["images"] or 0 for item in results]

    analysis = build_experiment_analysis(results)

    return render_template(
        "report.html",
        experiment=experiment,
        results=results,
        environment=environment,
        environment_count=environment_count,
        analysis=analysis,
        show_axe_failed_rules=as_bool(report_settings["show_axe_failed_rules"]),
        show_axe_needs_review=as_bool(report_settings["show_axe_needs_review"]),
        show_axe_densities=as_bool(report_settings["show_axe_densities"]),
        chart_labels=chart_labels,
        axe_values=axe_values,
        lighthouse_values=lighthouse_values,
        severity_totals=severity_totals,
        semantic_counts=semantic_counts,
        semantic_category_labels=semantic_category_labels,
        semantic_category_values=semantic_category_values,
        wave_category_totals=analysis["wave_categories"],
        execution_values=execution_values,
        dom_values=dom_values,
        image_values=image_values,
        tranco_sample=tranco_sample,
        tranco_quality=tranco_quality,
        tranco_recovery=tranco_recovery,
        tranco_active_stratum=tranco_active_stratum,
    )


@experiments_bp.route("/run", methods=["POST"])
def run_experiment():
    settings = get_settings()
    source_type = request.form.get("source_type", "url")
    if source_type not in {"url", "local_html", "tranco"}:
        source_type = "url"
    title = request.form.get("title", "").strip()
    urls_text = request.form.get("urls", "").strip()
    # Acquisition records and freezes the page. LLM work belongs to remediation.
    include_semantic = False
    include_wave = request.form.get("include_wave") == "on" and source_type in {"url", "tranco"}
    reuse_cached_results = request.form.get("reuse_cached_results") == "on"
    axe_standard = settings["axe_standard"]
    axe_include_best_practices = as_bool(settings["axe_include_best_practices"])
    language = session.get("language", "en")
    if include_wave and not settings["wave_api_key"]:
        flash(_("WAVE API is not configured in the environment."), "danger")
        return redirect(url_for("experiments.new_acquisition"))
    semantic_model = None
    stored_provider = None
    if not title:
        title = _("Evaluation %(timestamp)s", timestamp=now_local().strftime('%Y-%m-%d %H:%M:%S'))
    if len(title) > MAX_EXPERIMENT_NAME:
        flash(_("Experiment names can contain at most %(count)s characters.", count=MAX_EXPERIMENT_NAME), "danger")
        return redirect(url_for("experiments.new_acquisition"))

    dataset_metadata = None
    observations = []
    tranco_metadata = None
    if source_type == "local_html":
        archive = request.files.get("dataset_archive")
        html_files = request.files.getlist("html_files")
        resource_policy = request.form.get("resource_policy", "isolated")
        try:
            dataset_metadata, observations = import_dataset(
                archive, html_files, None, title, resource_policy
            )
        except DatasetImportError as error:
            flash(str(error), "danger")
            return redirect(url_for("experiments.new_acquisition"))
        urls = [item["served_url"] for item in observations]
    elif source_type == "tranco":
        resource_policy = "external"
        try:
            list_bytes, list_filename, list_id = fetch_latest_standard_list()
            ranking, frame_metadata = parse_tranco(list_bytes, list_filename)
            sampling_seed = request.form.get("tranco_seed", "").strip()
            try:
                sample_counts = {
                    label: int(request.form.get(f"tranco_count_{label}", "0"))
                    for label, _name, _lower, _upper in TRANCO_STRATA
                }
            except ValueError as error:
                raise TrancoImportError("Tranco sample size must be a whole number.") from error
            reserve_counts = {
                label: max(10, count) if count else 0
                for label, count in sample_counts.items()
            }
            candidates, strata = sample_tranco(
                ranking, list_id, sampling_seed, sample_counts, reserve_counts
            )
        except (TrancoImportError, ValueError) as error:
            flash(_(str(error)), "danger")
            return redirect(url_for("experiments.new_acquisition"))
        selected = [item for item in candidates if item["role"] == "selected"]
        urls = [item["url"] for item in selected]
        tranco_metadata = {
            **frame_metadata, "list_id": list_id, "sampling_seed": sampling_seed,
            "sample_per_stratum": max(sample_counts.values()),
            "reserve_per_stratum": max(reserve_counts.values()),
            "strata": strata, "candidates": candidates,
        }
    else:
        resource_policy = "external"
        dataset_text = urls_text or settings["internal_dataset_urls"]
        urls = [ensure_http_scheme(line) for line in dataset_text.splitlines() if line.strip()]
        if not urls:
            flash(_("No URLs were provided and no valid internal dataset was found."), "danger")
            return redirect(url_for("experiments.new_acquisition"))

    signature = evaluation_signature(
        settings, include_wave, include_semantic, stored_provider,
        semantic_model, axe_standard,
    )

    conn = get_connection()
    cursor = conn.cursor()
    try:
        dataset_id = None
        if dataset_metadata:
            cursor.execute(
                """
                INSERT INTO datasets (
                    title, storage_key, content_sha256, resource_policy,
                    observation_count, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    title, dataset_metadata["storage_key"],
                    dataset_metadata["content_sha256"], resource_policy,
                    len(observations), now_local(),
                ),
            )
            dataset_id = cursor.lastrowid
            for observation in observations:
                cursor.execute(
                    """
                    INSERT INTO dataset_observations (
                        dataset_id, relative_path, observation_key, pair_key,
                        condition_label, stratum, expected_label, content_sha256,
                        served_url, display_name, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        dataset_id, observation["path"], observation["observation_id"],
                        observation["pair_id"] or None, observation["condition"] or None,
                        observation["stratum"] or None,
                        int(observation["expected_label"]) if observation["expected_label"] else None,
                        observation["content_sha256"], observation["served_url"],
                        observation.get("display_name"), now_local(),
                    ),
                )
        cursor.execute(
            """
            INSERT INTO experiments (
            title, urls, include_semantic, include_wave, semantic_provider,
            semantic_model, axe_standard, axe_include_best_practices,
            reuse_cached_results, evaluation_signature, experiment_origin,
            source_type, dataset_id, resource_policy, language, status, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'evaluation', %s, %s, %s, %s, 'queued', %s)
            """,
            (
            title, "\n".join(urls), include_semantic, include_wave,
            stored_provider, semantic_model, axe_standard,
            axe_include_best_practices, reuse_cached_results, signature,
            source_type, dataset_id, resource_policy, language, now_local(),
            ),
        )
        experiment_id = cursor.lastrowid
        if tranco_metadata:
            cursor.execute(
                """
                INSERT INTO tranco_samples (
                    experiment_id, list_id, list_sha256, source_filename,
                    frame_size, sampling_seed, sample_per_stratum,
                    reserve_per_stratum, strata, candidates, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    experiment_id, tranco_metadata["list_id"],
                    tranco_metadata["list_sha256"], tranco_metadata["source_filename"],
                    tranco_metadata["frame_size"], tranco_metadata["sampling_seed"],
                    tranco_metadata["sample_per_stratum"],
                    tranco_metadata["reserve_per_stratum"],
                    json.dumps(tranco_metadata["strata"]),
                    json.dumps(tranco_metadata["candidates"]), now_local(),
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        if dataset_metadata:
            remove_dataset(dataset_metadata["storage_key"])
        raise
    cursor.close()
    conn.close()
    flash(_("The evaluation experiment was queued and will continue in the background."), "success")
    return redirect(url_for("experiments.experiment_report", experiment_id=experiment_id))


@experiments_bp.route("/run-sync", methods=["POST"])
def run_experiment_sync():
    settings = get_settings()
    title = request.form.get("title", "").strip()
    urls_text = request.form.get("urls", "").strip()
    # Semantic LLM evaluation has been retired; preserve legacy columns only
    # so historical experiments remain readable.
    include_semantic = False
    include_wave = request.form.get("include_wave") == "on"
    axe_standard = settings["axe_standard"]
    axe_include_best_practices = as_bool(settings["axe_include_best_practices"])
    language = session.get("language", "en")
    if include_wave and not settings["wave_api_key"]:
        flash(_("WAVE API is not configured in the environment."), "danger")
        return redirect(url_for("experiments.new_acquisition"))
    semantic_model = None
    stored_provider = None

    if not title:
        title = _("Evaluation %(timestamp)s", timestamp=now_local().strftime('%Y-%m-%d %H:%M:%S'))

    dataset_text = urls_text or settings["internal_dataset_urls"]
    urls = [ensure_http_scheme(line) for line in dataset_text.splitlines() if line.strip()]

    if not urls:
        flash(_("No URLs were provided and no valid internal dataset was found."), "danger")
        return redirect(url_for("experiments.new_acquisition"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO experiments (
            title, urls, include_semantic, include_wave, semantic_provider,
            semantic_model, axe_standard, axe_include_best_practices,
            status, created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        title,
        "\n".join(urls),
        include_semantic,
        include_wave,
        stored_provider,
        semantic_model,
        axe_standard,
        axe_include_best_practices,
        "running",
        now_local()
    ))

    experiment_id = cursor.lastrowid
    conn.commit()

    try:
        response = requests.post(
            f"{current_app.config['EVALUATOR_URL']}/evaluate",
            json={
                "experiment_id": experiment_id,
                "urls": urls,
                "include_semantic": include_semantic,
                "include_wave": include_wave,
                "language": language,
                "semantic_provider": stored_provider,
                "semantic_model": semantic_model,
                "axe_standard": axe_standard,
                "axe_include_best_practices": axe_include_best_practices,
                "runtime_config": evaluator_runtime_config(settings),
            },
            timeout=900
        )

        response.raise_for_status()
        payload = response.json()

        environment = payload.get("environment", {})

        cursor.execute("""
            INSERT INTO experiment_environment (
                experiment_id,
                docker_web_image,
                docker_evaluator_image,
                python_version,
                node_version,
                chromium_version,
                axe_version,
                lighthouse_version,
                axe_standard,
                axe_include_best_practices,
                axe_counting_mode,
                app_timezone,
                openai_model,
                llm_provider,
                llm_model,
                wave_api_version,
                wave_report_type,
                wave_eval_delay_ms,
                page_load_timeout_ms,
                network_idle_timeout_ms,
                page_settle_delay_ms,
                dom_stability_window_ms,
                dom_stability_timeout_ms,
                lazy_load_scroll,
                scroll_step_px,
                scroll_delay_ms,
                max_scroll_steps,
                evaluator_concurrency,
                execution_seconds,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            experiment_id,
            environment.get("docker_web_image"),
            environment.get("docker_evaluator_image"),
            environment.get("python_version"),
            environment.get("node_version"),
            environment.get("chromium_version"),
            environment.get("axe_version"),
            environment.get("lighthouse_version"),
            environment.get("axe_standard"),
            environment.get("axe_include_best_practices"),
            environment.get("axe_counting_mode"),
            environment.get("app_timezone"),
            environment.get("openai_model"),
            environment.get("llm_provider"),
            environment.get("llm_model"),
            environment.get("wave_api_version"),
            environment.get("wave_report_type"),
            environment.get("wave_eval_delay_ms"),
            environment.get("page_load_timeout_ms"),
            environment.get("network_idle_timeout_ms"),
            environment.get("page_settle_delay_ms"),
            environment.get("dom_stability_window_ms"),
            environment.get("dom_stability_timeout_ms"),
            environment.get("lazy_load_scroll"),
            environment.get("scroll_step_px"),
            environment.get("scroll_delay_ms"),
            environment.get("max_scroll_steps"),
            environment.get("evaluator_concurrency"),
            environment.get("execution_seconds"),
            now_local()
        ))

        for item in payload.get("results", []):
            if item.get("status") == "completed":
                semantic = item.get("semantic", {})
                wave = item.get("wave", {})
                metrics = item.get("html_metrics", {})
                load_metadata = item.get("load_metadata", {})

                cursor.execute("""
                    INSERT INTO experiment_results (
                        experiment_id, url, status,
                        axe_violations, axe_critical, axe_serious,
                        axe_moderate, axe_minor,
                        axe_failed_rules, axe_critical_rules, axe_serious_rules,
                        axe_moderate_rules, axe_minor_rules,
                        axe_needs_review, axe_needs_review_rules,
                        axe_best_practice_issues, axe_best_practice_rules,
                        axe_wcag_violations, axe_wcag_critical, axe_wcag_serious,
                        axe_wcag_moderate, axe_wcag_minor, axe_wcag_failed_rules, axe_wcag_needs_review,
                        lighthouse_score,
                        wave_status, wave_errors, wave_contrast_errors, wave_alerts,
                        wave_features, wave_structure, wave_aria, wave_aim_score,
                        wave_total_elements, wave_raw_path, wave_error_message,
                        semantic_status, semantic_risk_level, semantic_summary, semantic_findings,
                        html_size, dom_nodes, images, images_without_alt, links, buttons,
                        forms, inputs, headings, h1_count, language_declared,
                        has_main_landmark, has_nav_landmark, has_header_landmark, has_footer_landmark,
                        execution_seconds,
                        network_idle_reached, lazy_scroll_steps,
                        dom_stable, dom_stability_wait_ms,
                        screenshot_path,
                        screenshot_mode,
                        axe_raw_path, lighthouse_raw_path, semantic_raw_path,
                        created_at
                    )
                    VALUES (
                        %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s,
                        %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, CAST(%s AS JSON),
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s,
                        %s, %s, %s, %s,
                        %s,
                        %s,
                        %s, %s, %s,
                        %s
                    )
                """, (
                    experiment_id,
                    item.get("url"),
                    "completed",
                    item.get("axe", {}).get("violations", 0),
                    item.get("axe", {}).get("critical", 0),
                    item.get("axe", {}).get("serious", 0),
                    item.get("axe", {}).get("moderate", 0),
                    item.get("axe", {}).get("minor", 0),
                    item.get("axe", {}).get("failed_rules", 0),
                    item.get("axe", {}).get("critical_rules", 0),
                    item.get("axe", {}).get("serious_rules", 0),
                    item.get("axe", {}).get("moderate_rules", 0),
                    item.get("axe", {}).get("minor_rules", 0),
                    item.get("axe", {}).get("needs_review", 0),
                    item.get("axe", {}).get("needs_review_rules", 0),
                    item.get("axe", {}).get("best_practice_issues", 0),
                    item.get("axe", {}).get("best_practice_rules", 0),
                    item.get("axe", {}).get("wcag_violations", 0),
                    item.get("axe", {}).get("wcag_critical", 0),
                    item.get("axe", {}).get("wcag_serious", 0),
                    item.get("axe", {}).get("wcag_moderate", 0),
                    item.get("axe", {}).get("wcag_minor", 0),
                    item.get("axe", {}).get("wcag_failed_rules", 0),
                    item.get("axe", {}).get("wcag_needs_review", 0),
                    item.get("lighthouse", {}).get("accessibility_score"),
                    wave.get("status"),
                    wave.get("errors", 0),
                    wave.get("contrast_errors", 0),
                    wave.get("alerts", 0),
                    wave.get("features", 0),
                    wave.get("structure", 0),
                    wave.get("aria", 0),
                    wave.get("aim_score"),
                    wave.get("total_elements", 0),
                    wave.get("raw_path"),
                    wave.get("error"),
                    semantic.get("status"),
                    semantic.get("risk_level"),
                    semantic.get("summary"),
                    json.dumps(semantic.get("findings", []), ensure_ascii=False),
                    metrics.get("html_size", 0),
                    metrics.get("dom_nodes", 0),
                    metrics.get("images", 0),
                    metrics.get("images_without_alt", 0),
                    metrics.get("links", 0),
                    metrics.get("buttons", 0),
                    metrics.get("forms", 0),
                    metrics.get("inputs", 0),
                    metrics.get("headings", 0),
                    metrics.get("h1_count", 0),
                    metrics.get("language_declared"),
                    metrics.get("has_main_landmark", False),
                    metrics.get("has_nav_landmark", False),
                    metrics.get("has_header_landmark", False),
                    metrics.get("has_footer_landmark", False),
                    item.get("execution_seconds"),
                    load_metadata.get("network_idle_reached"),
                    load_metadata.get("scroll_steps"),
                    load_metadata.get("dom_stable"),
                    load_metadata.get("dom_stability_wait_ms"),
                    item.get("screenshot_path"),
                    item.get("screenshot_mode"),
                    item.get("axe", {}).get("raw_path"),
                    item.get("lighthouse", {}).get("raw_path"),
                    semantic.get("raw_path"),
                    now_local()
                ))
            else:
                cursor.execute("""
                    INSERT INTO experiment_results (
                        experiment_id, url, status, error_message, execution_seconds, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    experiment_id,
                    item.get("url"),
                    "failed",
                    item.get("error"),
                    item.get("execution_seconds"),
                    now_local()
                ))

        cursor.execute("""
            UPDATE experiments
            SET status = %s, completed_at = %s
            WHERE id = %s
        """, ("completed", now_local(), experiment_id))

        conn.commit()
        flash(_("Accessibility evaluation experiment completed successfully."), "success")

    except Exception as error:
        cursor.execute("""
            UPDATE experiments
            SET status = %s, completed_at = %s
            WHERE id = %s
        """, ("failed", now_local(), experiment_id))

        conn.commit()
        flash(_("The accessibility evaluation experiment could not be completed: %(error)s", error=error), "danger")

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("experiments.experiment_report", experiment_id=experiment_id))


@experiments_bp.route("/experiments/<int:experiment_id>/csv", methods=["GET"])
def download_experiment_csv(experiment_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT r.*, COALESCE(r.display_name, o.display_name, o.observation_key, r.url) AS observation_id,
               o.relative_path, o.pair_key, o.condition_label, o.stratum,
               o.expected_label
        FROM experiment_results r
        LEFT JOIN dataset_observations o ON o.id = r.dataset_observation_id
        WHERE r.experiment_id = %s
        ORDER BY r.id ASC
    """, (experiment_id,))
    results = [project_wcag(row) for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    for item in results:
        findings = item.get("semantic_findings")
        if isinstance(findings, str):
            try:
                item["semantic_findings"] = json.loads(findings)
            except (TypeError, ValueError):
                item["semantic_findings"] = []
        elif findings is None:
            item["semantic_findings"] = []

    analysis = build_experiment_analysis(results)
    derived_by_result_id = {
        page["result_id"]: page for page in analysis["ranked_pages"]
    }
    paired_by_result_id = {}
    for pair in analysis["paired"]["pairs"]:
        paired_by_result_id[pair["original_result_id"]] = pair
        paired_by_result_id[pair["corrected_result_id"]] = pair

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "experiment_id",
        "url",
        "observation_id",
        "relative_path",
        "pair_id",
        "condition",
        "stratum",
        "expected_label",
        "content_sha256",
        "paired_axe_issue_reduction",
        "paired_lighthouse_gain",
        "status",
        "cross_tool_composite_score",
        "cross_tool_disagreement",
        "axe_issue_density_per_1000_dom_nodes",
        "axe_weighted_impact_density",
        "axe_issue_instances",
        "axe_failed_rules",
        "axe_needs_review_instances",
        "axe_needs_review_rules",
        "axe_best_practice_issues",
        "axe_best_practice_rules",
        "axe_combined_issue_instances",
        "axe_counting_policy",
        "axe_critical",
        "axe_serious",
        "axe_moderate",
        "axe_minor",
        "lighthouse_score",
        "wave_status",
        "wave_errors",
        "wave_contrast_errors",
        "wave_alerts",
        "wave_features",
        "wave_structure",
        "wave_aria",
        "wave_aim_score",
        "wave_total_elements",
        "wave_credits_used",
        "wave_cost_usd",
        "wave_error_message",
        "semantic_status",
        "semantic_findings_count",
        "semantic_high_findings",
        "semantic_medium_findings",
        "semantic_low_findings",
        "semantic_input_tokens",
        "semantic_output_tokens",
        "semantic_total_tokens",
        "semantic_cost_usd",
        "total_api_cost_usd",
        "semantic_risk_level",
        "semantic_summary",
        "html_size",
        "dom_nodes",
        "images",
        "images_without_alt",
        "links",
        "buttons",
        "forms",
        "inputs",
        "headings",
        "h1_count",
        "language_declared",
        "has_main_landmark",
        "has_nav_landmark",
        "has_header_landmark",
        "has_footer_landmark",
        "execution_seconds"
        ,"network_idle_reached"
        ,"lazy_scroll_steps"
        ,"dom_stable"
        ,"dom_stability_wait_ms"
    ])

    for item in results:
        derived = derived_by_result_id.get(item.get("id"), {})
        paired = paired_by_result_id.get(item.get("id"), {})
        writer.writerow([
            experiment_id,
            item.get("url"),
            item.get("observation_id"),
            item.get("relative_path"),
            item.get("pair_key"),
            item.get("condition_label"),
            item.get("stratum"),
            item.get("expected_label"),
            item.get("content_sha256"),
            paired.get("axe_reduction"),
            paired.get("lighthouse_gain"),
            item.get("status"),
            derived.get("composite_score"),
            derived.get("tool_disagreement"),
            derived.get("axe_density"),
            derived.get("weighted_density"),
            item.get("axe_violations"),
            item.get("axe_failed_rules"),
            item.get("axe_needs_review"),
            item.get("axe_needs_review_rules"),
            item.get("axe_best_practice_issues"),
            item.get("axe_best_practice_rules"),
            item.get("axe_combined_violations"),
            item.get("axe_counting_policy"),
            item.get("axe_critical"),
            item.get("axe_serious"),
            item.get("axe_moderate"),
            item.get("axe_minor"),
            item.get("lighthouse_score"),
            item.get("wave_status"),
            item.get("wave_errors"),
            item.get("wave_contrast_errors"),
            item.get("wave_alerts"),
            item.get("wave_features"),
            item.get("wave_structure"),
            item.get("wave_aria"),
            item.get("wave_aim_score"),
            item.get("wave_total_elements"),
            item.get("wave_credits_used"),
            item.get("wave_cost_usd"),
            item.get("wave_error_message"),
            item.get("semantic_status"),
            len(item.get("semantic_findings") or []) if item.get("semantic_status") == "completed" else None,
            sum(1 for finding in (item.get("semantic_findings") or []) if finding.get("severity") == "high") if item.get("semantic_status") == "completed" else None,
            sum(1 for finding in (item.get("semantic_findings") or []) if finding.get("severity") == "medium") if item.get("semantic_status") == "completed" else None,
            sum(1 for finding in (item.get("semantic_findings") or []) if finding.get("severity") == "low") if item.get("semantic_status") == "completed" else None,
            item.get("semantic_input_tokens"),
            item.get("semantic_output_tokens"),
            item.get("semantic_total_tokens"),
            item.get("semantic_cost_usd"),
            round(
                float(item.get("wave_cost_usd") or 0)
                + float(item.get("semantic_cost_usd") or 0),
                6,
            ),
            item.get("semantic_risk_level"),
            item.get("semantic_summary"),
            item.get("html_size"),
            item.get("dom_nodes"),
            item.get("images"),
            item.get("images_without_alt"),
            item.get("links"),
            item.get("buttons"),
            item.get("forms"),
            item.get("inputs"),
            item.get("headings"),
            item.get("h1_count"),
            item.get("language_declared"),
            item.get("has_main_landmark"),
            item.get("has_nav_landmark"),
            item.get("has_header_landmark"),
            item.get("has_footer_landmark"),
            item.get("execution_seconds")
            ,item.get("network_idle_reached")
            ,item.get("lazy_scroll_steps")
            ,item.get("dom_stable")
            ,item.get("dom_stability_wait_ms")
        ])

    csv_content = output.getvalue()
    output.close()

    filename = f"experiment_{experiment_id}_results.csv"

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@experiments_bp.route("/experiments/<int:experiment_id>/raw/<int:result_id>/<tool>", methods=["GET"])
def download_raw_result(experiment_id, result_id, tool):
    allowed_tools = {
        "axe": "axe_raw_path",
        "lighthouse": "lighthouse_raw_path",
        "wave": "wave_raw_path",
        "semantic": "semantic_raw_path"
    }

    if tool not in allowed_tools:
        flash(_("Invalid tool requested for download."), "danger")
        return redirect(url_for("experiments.experiment_report", experiment_id=experiment_id))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, experiment_id, url,
               axe_raw_path, lighthouse_raw_path, wave_raw_path, semantic_raw_path
        FROM experiment_results
        WHERE id = %s AND experiment_id = %s
    """, (result_id, experiment_id))

    result = cursor.fetchone()

    cursor.close()
    conn.close()

    if not result:
        flash(_("The requested result was not found."), "danger")
        return redirect(url_for("experiments.experiment_report", experiment_id=experiment_id))

    file_path = result.get(allowed_tools[tool])

    if not file_path or not os.path.exists(file_path):
        flash(_("The requested file does not exist or was not generated."), "warning")
        return redirect(url_for("experiments.experiment_report", experiment_id=experiment_id))

    filename = f"experiment_{experiment_id}_result_{result_id}_{tool}.json"

    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename,
        mimetype="application/json"
    )


@experiments_bp.route("/experiments/<int:experiment_id>/screenshot/<int:result_id>", methods=["GET"])
def experiment_screenshot(experiment_id, result_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT screenshot_path
        FROM experiment_results
        WHERE id = %s AND experiment_id = %s
        """,
        (result_id, experiment_id),
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    screenshot_path = result.get("screenshot_path") if result else None
    allowed_root = os.path.realpath("/results/raw")
    resolved_path = os.path.realpath(screenshot_path) if screenshot_path else ""
    if (
        not resolved_path.startswith(f"{allowed_root}{os.sep}")
        or not os.path.isfile(resolved_path)
    ):
        return Response(status=404)

    return send_file(resolved_path, mimetype="image/jpeg", conditional=True)
