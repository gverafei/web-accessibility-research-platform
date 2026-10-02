import hashlib
import json
from urllib.parse import urlsplit

from flask import Blueprint, Response, jsonify, request, send_file, url_for
from flask_babel import force_locale, gettext

from database import get_connection
from result_portability import evaluation_signature, normalize_url
from routes.remediation import now_local
from browser_extension_config import PRIORITIES, extension_catalog, extension_configuration
from remediation_model_choices import model_choice, frozen_model_configuration
from remediation_recipes import automatic_recipe
from settings import get_settings
from browser_extension_results import TERMINAL, candidate_path, reusable_request, stored_measurements
from remediation_control_copy import control_copy


extension_api_bp = Blueprint("extension_api", __name__, url_prefix="/api/browser-extension")


@extension_api_bp.after_request
def allow_local_extension(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@extension_api_bp.route("/<path:_path>", methods=["OPTIONS"])
def preflight(_path):
    return ("", 204)


@extension_api_bp.get("/configuration")
def configuration():
    catalog = extension_catalog(get_settings())
    catalog['ui_copy'] = {}
    for locale in ('en', 'es'):
        with force_locale(locale):
            catalog['ui_copy'][locale] = control_copy(gettext)
    return jsonify(catalog)


def create_run(cursor, result_id, url, config, settings):
    choice = config.get('model_configuration') or model_choice(config["selected_model"], settings)
    preservation_level = config["preservation_level"]
    priority = PRIORITIES[preservation_level]
    execution_mode = "regenerate_refine" if priority >= 75 else "iterative"
    # Freeze targets at request submission, even when acquisition finishes later.
    # Legacy pending requests predate configurable targets and keep 94/3.
    targets = config.get('research_targets')
    target_settings = ({'remediation_min_lighthouse': targets['lighthouse'],
                        'remediation_max_axe': targets['axe']} if targets else {})
    recipe = automatic_recipe(priority, execution_mode, settings=target_settings)
    temperature, iterations, lighthouse, axe, review, cost, seconds, rag_k = (
        recipe[key] for key in ("temperature", "iterations", "lighthouse", "axe", "review", "cost", "seconds", "rag_top_k"))
    tier = choice["tier"]
    model = choice["model"]
    provider = model.split("/", 1)[0]
    wave_enabled = False  # WAVE is reserved for separate evaluations.
    title = f"Browser remediation · {urlsplit(url).netloc or url}"[:180]
    representation = "markdown" if priority >= 90 else "html"
    cursor.execute("""INSERT INTO remediation_runs
        (source_result_id,template_id,title,transformation_format,generator_provider,generator_model,
         reviewer_provider,reviewer_model,max_iterations,min_lighthouse,max_axe,min_aim,status,created_at,
         accessibility_priority,temperature,template_selection,template_rationale,use_wave,
         model_selection_mode,model_cost_tier,allowed_models_json,max_dom_distance,enforce_dom_distance,
         review_policy,max_cost_usd,max_execution_seconds,use_rag,rag_top_k)
        VALUES (%s,NULL,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
        'queued',%s,%s,%s,%s,%s,%s,'user',%s,%s,%s,FALSE,%s,%s,%s,%s,%s)""", (
        result_id, title, representation, provider, model, provider, model, iterations, lighthouse, axe,
        (7, 8, 9, 9.5, 10)[preservation_level] if wave_enabled else None,
        now_local(), priority, temperature, "vera_reference" if priority >= 75 else "component_knowledge",
        "Explicit extension model and shared platform intervention policy; Bootstrap design base for regeneration.",
        wave_enabled, tier, json.dumps([model]), priority,
        review, cost, seconds, config["use_rag"], rag_k,
    ))
    run_id = cursor.lastrowid
    cursor.execute("UPDATE remediation_runs SET model_config_json=%s WHERE id=%s", (json.dumps(frozen_model_configuration(choice)), run_id))
    cursor.execute("UPDATE remediation_runs SET execution_mode=%s,use_expert_settings=FALSE WHERE id=%s", (execution_mode, run_id))
    if model.startswith("ollama/"):
        from local_llm import local_configuration
        local = config.get('local_llm_configuration') or local_configuration(settings)
        cursor.execute("UPDATE remediation_runs SET local_llm_config_json=%s WHERE id=%s", (json.dumps(local), run_id))
    return run_id


@extension_api_bp.post("/requests")
def create_request():
    payload = request.get_json(silent=True) or {}
    raw_url = str(payload.get("url") or "").strip()
    parsed = urlsplit(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return jsonify({"error": "Open a normal HTTP or HTTPS page first."}), 400
    normalized = normalize_url(raw_url)
    force_rerun = payload.get('force_rerun', False)
    if not isinstance(force_rerun, bool):
        return jsonify({'error': 'force_rerun must be a JSON boolean.'}), 400
    settings = get_settings()
    try:
        config = extension_configuration(payload, settings)
    except (ValueError, TypeError) as error:
        return jsonify({"error": str(error)}), 400
    preservation = config["preservation_level"]
    choice = config['model_configuration']
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    try:
        # Serialize submissions for one URL, including simultaneous panel clicks.
        cursor.execute('SELECT GET_LOCK(%s,10) locked', ('extension:' + hashlib.sha256(normalized.encode()).hexdigest()[:48],))
        if not (cursor.fetchone() or {}).get('locked'):
            return jsonify({'error': 'Another request is being submitted. Please retry.'}), 409
        run_id = None
        experiment_id = None
        result = None
        if not force_rerun:
            cursor.execute("""SELECT id FROM experiment_results
                WHERE normalized_url=%s AND status='completed' AND source_snapshot_path IS NOT NULL
                ORDER BY evaluated_at DESC,id DESC LIMIT 1""", (normalized,))
            result = cursor.fetchone()
            existing = reusable_request(cursor, normalized, result['id'] if result else None, config)
            if existing:
                return jsonify({'id': existing['id'], 'status': existing.get('run_status') or 'acquiring',
                                'reused': True}), 200
        if result:
            run_id = create_run(cursor, result["id"], raw_url, config, settings)
            state = "remediating"
        else:
            settings = get_settings()
            signature = evaluation_signature(
                settings, False, False, None, None, "wcag22aa"
            )
            cursor.execute("""INSERT INTO experiments
                (title,urls,include_semantic,include_wave,axe_standard,axe_include_best_practices,
                 reuse_cached_results,evaluation_signature,experiment_origin,language,status,created_at,
                 source_type,resource_policy)
                VALUES (%s,%s,FALSE,FALSE,'wcag22aa',FALSE,%s,%s,'browser_extension','en','queued',
                        %s,'url','external')""",
                (f"Browser acquisition · {parsed.netloc}{parsed.path or '/'}"[:255], raw_url, not force_rerun,
                 signature, now_local()))
            experiment_id = cursor.lastrowid; state = "acquiring"
        cursor.execute("""INSERT INTO browser_remediation_requests
            (url,normalized_url,acquisition_experiment_id,remediation_run_id,model_cost_tier,
             preservation_level,use_rag,use_wave,status,created_at,updated_at,configuration_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (raw_url, normalized, experiment_id, run_id, choice["tier"], preservation,
             config["use_rag"], False, state, now_local(), now_local(), json.dumps(config)))
        request_id = cursor.lastrowid; conn.commit()
        return jsonify({"id": request_id, "status": state, "reused": False}), 202
    finally:
        cursor.close(); conn.close()  # Releases the URL submission lock, including on errors.


def request_payload(cursor, item):
    if not item.get("remediation_run_id"):
        cursor.execute("SELECT status FROM experiments WHERE id=%s", (item["acquisition_experiment_id"],))
        experiment = cursor.fetchone()
        if not experiment:
            return {"status": "failed", "message": "The acquisition record was removed."}
        if experiment["status"] == "completed":
            cursor.execute("""SELECT id FROM experiment_results WHERE experiment_id=%s
                AND status='completed' AND source_snapshot_path IS NOT NULL ORDER BY id DESC LIMIT 1""",
                (item["acquisition_experiment_id"],))
            result = cursor.fetchone()
            if not result:
                cursor.execute("SELECT error_message FROM experiment_results WHERE experiment_id=%s ORDER BY id DESC LIMIT 1", (item["acquisition_experiment_id"],))
                failed = cursor.fetchone() or {}
                return {"status": "failed", "message": failed.get("error_message") or "The page could not be acquired."}
            if not item.get("configuration_json"):
                return {"status": "failed", "message": "Legacy extension configuration: reload the extension and submit an explicit model selection."}
            try:
                settings = get_settings()
                config = json.loads(item["configuration_json"])
                if not config.get('model_configuration'):
                    raise ValueError('The request has no frozen model configuration. Submit a new request.')
                run_id = create_run(cursor, result["id"], item["url"], config, settings)
            except (ValueError, TypeError) as error:
                return {"status": "failed", "message": str(error)}
            cursor.execute("UPDATE browser_remediation_requests SET remediation_run_id=%s,status='remediating',updated_at=%s WHERE id=%s", (run_id, now_local(), item["id"]))
            item["remediation_run_id"] = run_id
        elif experiment["status"] == "failed":
            return {"status": "failed", "message": "Acquisition failed."}
        else:
            return {"status": "acquiring", "phase": "Acquire", "progress": 10,
                    "message": "Capturing and evaluating the original page."}
    cursor.execute("SELECT * FROM remediation_runs WHERE id=%s", (item["remediation_run_id"],))
    run = cursor.fetchone()
    if not run:
        return {"status": "failed", "message": "The remediation run was removed."}
    result = {"status": run["status"], "phase": run.get("current_phase"),
              "progress": run.get("progress_percent") or 0,
              "message": run.get("progress_message") or "Waiting for the remediation worker.",
              "run_id": run["id"]}
    candidate_iteration = run.get("accepted_iteration_id")
    if not candidate_iteration and run["status"] in {"metrics_not_achieved", "review_not_achieved", "failed"}:
        cursor.execute("SELECT id FROM remediation_iterations WHERE run_id=%s AND output_path IS NOT NULL ORDER BY iteration_number DESC,id DESC LIMIT 1", (run["id"],))
        latest = cursor.fetchone()
        candidate_iteration = latest["id"] if latest else None
    if candidate_iteration:
        result["candidate_url"] = url_for("extension_api.request_candidate", request_id=item["id"], _external=True)
        result["candidate_accepted"] = run['status'] == 'accepted'
        result["candidate_available"] = bool(candidate_iteration)
    if run['status'] in TERMINAL:
        result['measurements'] = stored_measurements(cursor, run, candidate_iteration)
        result['report_url'] = url_for('remediation.run_detail', run_id=run['id'], _external=True)
    return result


@extension_api_bp.get("/requests/<int:request_id>")
def get_request(request_id):
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM browser_remediation_requests WHERE id=%s FOR UPDATE", (request_id,))
    item = cursor.fetchone()
    if not item:
        cursor.close(); conn.close(); return jsonify({"error": "Request not found."}), 404
    result = request_payload(cursor, item)
    cursor.execute("UPDATE browser_remediation_requests SET status=%s,error_message=%s,updated_at=%s WHERE id=%s",
                   (result["status"], result.get("message") if result["status"] == "failed" else None, now_local(), request_id))
    conn.commit(); cursor.close(); conn.close()
    return jsonify({"id": request_id, "url": item["url"], **result})


@extension_api_bp.get("/requests/latest")
def latest_request():
    raw_url = str(request.args.get("url") or "").strip()
    parsed = urlsplit(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return jsonify({"error": "A valid HTTP or HTTPS URL is required."}), 400
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("""SELECT * FROM browser_remediation_requests
        WHERE normalized_url=%s ORDER BY id DESC LIMIT 1 FOR UPDATE""", (normalize_url(raw_url),))
    item = cursor.fetchone()
    if not item:
        cursor.close(); conn.close(); return jsonify({"error": "Request not found."}), 404
    result = request_payload(cursor, item)
    cursor.execute("UPDATE browser_remediation_requests SET status=%s,error_message=%s,updated_at=%s WHERE id=%s",
                   (result["status"], result.get("message") if result["status"] == "failed" else None, now_local(), item["id"]))
    conn.commit(); cursor.close(); conn.close()
    return jsonify({"id": item["id"], "url": item["url"], **result})


@extension_api_bp.get("/requests/<int:request_id>/candidate")
def request_candidate(request_id):
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT remediation_run_id FROM browser_remediation_requests WHERE id=%s", (request_id,))
    item = cursor.fetchone()
    if not item or not item.get("remediation_run_id"):
        cursor.close(); conn.close(); return Response(status=404)
    cursor.execute("SELECT accepted_iteration_id FROM remediation_runs WHERE id=%s", (item["remediation_run_id"],))
    run = cursor.fetchone(); iteration_id = run.get("accepted_iteration_id") if run else None
    if not iteration_id:
        cursor.execute("SELECT id FROM remediation_iterations WHERE run_id=%s AND output_path IS NOT NULL ORDER BY iteration_number DESC,id DESC LIMIT 1", (item["remediation_run_id"],))
        latest = cursor.fetchone(); iteration_id = latest.get("id") if latest else None
    cursor.execute("SELECT output_path FROM remediation_iterations WHERE id=%s AND run_id=%s", (iteration_id, item["remediation_run_id"]))
    iteration = cursor.fetchone(); cursor.close(); conn.close()
    path = candidate_path(iteration.get('output_path') if iteration else None)
    if not path:
        return Response(status=404)
    return send_file(path, mimetype="text/html", conditional=True)
