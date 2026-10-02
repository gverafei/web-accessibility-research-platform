import json
import statistics
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_babel import gettext as _

from database import get_connection
from axe_metrics import project_wcag, persist_metrics
from settings import get_settings


comparisons_bp = Blueprint("comparisons", __name__)
MAX_COMPARISON_MEMBERS = 1000
MAX_OBSERVATION_NAME = 160
MAX_GROUP_LABEL = 80
MAX_PAIR_KEY = 120
MAX_COMPARISON_NAME = 160
MAX_INDIVIDUAL_CHART_PAGES = 20


def now_local():
    return datetime.now(ZoneInfo(get_settings()["app_timezone"])).replace(tzinfo=None)


def quantiles(values):
    ordered = sorted(float(value) for value in values if value is not None)
    if not ordered:
        return None
    if len(ordered) == 1:
        return {"min": ordered[0], "q1": ordered[0], "median": ordered[0], "q3": ordered[0], "max": ordered[0], "n": 1}
    quartiles = statistics.quantiles(ordered, n=4, method="inclusive")
    return {"min": ordered[0], "q1": quartiles[0], "median": statistics.median(ordered),
            "q3": quartiles[2], "max": ordered[-1], "n": len(ordered)}


def comparison_analysis(members):
    members = [project_wcag(row) for row in members]
    # Each metric uses its own complete cases. Missing optional-tool data is
    # never interpreted as zero and does not exclude the observation elsewhere.
    completed = list(members)
    groups = defaultdict(list)
    multi_pair = len({str(row.get("pair_key") or "").strip() for row in completed
                      if row.get("is_baseline") and str(row.get("pair_key") or "").strip()}) > 1
    has_groups = any((row.get("group_label") or "").strip() or (row.get("group_label_2") or "").strip()
                     for row in completed if not row.get("is_baseline"))
    candidate_count = sum(not row.get("is_baseline") for row in completed)
    requires_grouping = candidate_count > MAX_INDIVIDUAL_CHART_PAGES and not has_groups
    for row in completed:
        if row.get("is_baseline") and not multi_pair:
            continue
        labels = [(row.get("group_label") or "").strip(), (row.get("group_label_2") or "").strip()]
        if has_groups:
            for label in dict.fromkeys(label for label in labels if label):
                groups[label].append(row)
        else:
            groups[_("All pages")].append(row)
    summaries = []
    for label, rows in sorted(groups.items()):
        def average(field):
            values = [float(row[field]) for row in rows if row.get(field) is not None]
            return round(statistics.fmean(values), 3) if values else None
        summaries.append({
            "label": label, "n": len(rows), "axe": average("axe_violations"),
            "lighthouse": average("lighthouse_score"), "wave": average("wave_errors"),
            "wave_contrast": average("wave_contrast_errors"),
            "wave_alerts": average("wave_alerts"), "wave_features": average("wave_features"),
            "llm": average("semantic_findings_count"),
            "tokens": average("semantic_total_tokens"),
            "axe_box": quantiles([row.get("axe_violations") for row in rows]),
            "lighthouse_box": quantiles([row.get("lighthouse_score") for row in rows]),
            "wave_box": quantiles([row.get("wave_errors") for row in rows]),
            "llm_box": quantiles([row.get("semantic_findings_count") for row in rows]),
            "tokens_box": quantiles([row.get("semantic_total_tokens") for row in rows]),
        })

    # Group 1 describes the condition (e.g. original/remediated), while
    # Group 2 describes the cohort (e.g. Tranco stratum). Keep both dimensions
    # for side-by-side charts instead of mixing cohorts into two global bars.
    cohort_groups = defaultdict(lambda: defaultdict(list))
    for row in completed:
        condition = (row.get("group_label") or "").strip()
        cohort = (row.get("group_label_2") or "").strip()
        if condition and cohort:
            cohort_groups[cohort][condition].append(row)
    baseline_conditions = {
        (row.get("group_label") or "").strip() for row in completed
        if row.get("is_baseline") and (row.get("group_label") or "").strip()
    }
    conditions = sorted(
        {condition for groups_by_condition in cohort_groups.values()
         for condition in groups_by_condition},
        key=lambda condition: (condition not in baseline_conditions, condition),
    )
    cohort_summary = []
    if len(cohort_groups) >= 2 and len(conditions) >= 2:
        tranco_order = {label: index for index, label in enumerate((
            "Global top 500", "Very high popularity", "High popularity",
            "Medium popularity", "Popularity tail"))}
        ordered_cohorts = sorted(cohort_groups.items(),
                                 key=lambda item: (tranco_order.get(item[0], len(tranco_order)), item[0]))
        for cohort, groups_by_condition in ordered_cohorts:
            values = {}
            for condition in conditions:
                rows = groups_by_condition.get(condition, [])
                values[condition] = {"n": len(rows)}
                for metric, field in (("axe", "axe_violations"),
                                      ("lighthouse", "lighthouse_score"),
                                      ("wave", "wave_errors"),
                                      ("llm", "semantic_findings_count")):
                    measured = [float(row[field]) for row in rows if row.get(field) is not None]
                    values[condition][metric] = round(statistics.fmean(measured), 3) if measured else None
            cohort_summary.append({"label": cohort, "conditions": values})

    deltas = []
    paired_sets = defaultdict(list)
    for member in completed:
        if (member.get("pair_key") or "").strip():
            paired_sets[member["pair_key"].strip()].append(member)
    valid_pairs = [rows for rows in paired_sets.values()
                   if sum(bool(row.get("is_baseline")) for row in rows) == 1
                   and any(not row.get("is_baseline") for row in rows)]
    if valid_pairs:
        comparisons = [(next(row for row in rows if row.get("is_baseline")), candidate)
                       for rows in valid_pairs for candidate in rows if not candidate.get("is_baseline")]
    else:
        baselines = [row for row in completed if row.get("is_baseline")]
        comparisons = ([(baselines[0], candidate) for candidate in completed
                        if candidate["id"] != baselines[0]["id"]]
                       if len(baselines) == 1 and not requires_grouping else [])
    for baseline, candidate in comparisons:
            candidate_groups = [label for label in ((candidate.get("group_label") or "").strip(),
                                (candidate.get("group_label_2") or "").strip()) if label]
            if has_groups and not candidate_groups:
                continue
            deltas.append({
                "pair_key": candidate.get("pair_key"),
                "baseline": baseline["display_name"], "candidate": candidate["display_name"],
                "groups": candidate_groups,
                "condition": (candidate.get("group_label") or "").strip(),
                "cohort": (candidate.get("group_label_2") or "").strip(),
                "baseline_axe": baseline.get("axe_violations"),
                "candidate_axe": candidate.get("axe_violations"),
                "baseline_lighthouse": baseline.get("lighthouse_score"),
                "candidate_lighthouse": candidate.get("lighthouse_score"),
                "axe_improvement": (baseline["axe_violations"] - candidate["axe_violations"])
                    if baseline.get("axe_violations") is not None and candidate.get("axe_violations") is not None else None,
                "lighthouse_improvement": (candidate["lighthouse_score"] - baseline["lighthouse_score"])
                    if baseline.get("lighthouse_score") is not None and candidate.get("lighthouse_score") is not None else None,
                "wave_improvement": (baseline["wave_errors"] - candidate["wave_errors"])
                    if baseline.get("wave_errors") is not None and candidate.get("wave_errors") is not None else None,
                "llm_improvement": (baseline["semantic_findings_count"] - candidate["semantic_findings_count"])
                    if baseline.get("semantic_findings_count") is not None and candidate.get("semantic_findings_count") is not None else None,
            })
    delta_groups = defaultdict(list)
    paired_cohorts = {row["cohort"] for row in deltas if row["cohort"]}
    paired_conditions = {row["condition"] for row in deltas if row["condition"]}
    for row in deltas:
        if paired_cohorts:
            if row["cohort"]:
                delta_groups[row["cohort"]].append(row)
        elif len(paired_conditions) > 1:
            if row["condition"]:
                delta_groups[row["condition"]].append(row)
        else:
            delta_groups[_('All pages')].append(row)
    improvement_boxes = []
    tranco_order = {label: index for index, label in enumerate((
        "Global top 500", "Very high popularity", "High popularity",
        "Medium popularity", "Popularity tail"))}
    for label, rows in sorted(delta_groups.items(),
                              key=lambda item: (tranco_order.get(item[0], len(tranco_order)), item[0])):
        improvement_boxes.append({
            "label": label,
            "axe": quantiles([row["axe_improvement"] for row in rows]),
            "lighthouse": quantiles([row["lighthouse_improvement"] for row in rows]),
            "wave": quantiles([row["wave_improvement"] for row in rows]),
            "llm": quantiles([row["llm_improvement"] for row in rows]),
        })
    heat_max = {
        field: max(1, max([float(row[field]) for row in completed if row.get(field) is not None] or [1]))
        for field in ("axe_violations", "lighthouse_score", "wave_errors", "wave_contrast_errors",
                      "wave_alerts", "wave_features", "semantic_findings_count", "semantic_total_tokens")
    }
    metric_fields = {
        "axe": "axe_violations", "lighthouse": "lighthouse_score",
        "wave": "wave_errors", "llm": "semantic_findings_count", "tokens": "semantic_total_tokens",
    }
    availability = {}
    for metric, field in metric_fields.items():
        populated_groups = {label for label, rows in groups.items() if any(row.get(field) is not None for row in rows)}
        paired_values = [row.get(f"{metric}_improvement") for row in deltas]
        availability[metric] = {
            "observations": sum(row.get(field) is not None for row in completed),
            "groups": len(populated_groups),
            "comparable": len(populated_groups) >= 2,
            "paired": sum(value is not None for value in paired_values),
        }
    cohort_matrix = []
    if len(conditions) == 2:
        baseline_condition, candidate_condition = conditions
        for row in cohort_summary:
            baseline = row["conditions"][baseline_condition]
            candidate = row["conditions"][candidate_condition]
            cohort_matrix.append({
                "label": row["label"],
                "baseline_condition": baseline_condition,
                "candidate_condition": candidate_condition,
                "baseline": baseline,
                "candidate": candidate,
                "axe_improvement": round(baseline["axe"] - candidate["axe"], 3)
                    if baseline["axe"] is not None and candidate["axe"] is not None else None,
                "lighthouse_improvement": round(candidate["lighthouse"] - baseline["lighthouse"], 3)
                    if baseline["lighthouse"] is not None and candidate["lighthouse"] is not None else None,
            })
    return {"summaries": summaries, "cohort_summary": cohort_summary,
            "cohort_matrix": cohort_matrix,
            "cohort_conditions": conditions, "deltas": deltas, "improvement_boxes": improvement_boxes,
            "heat_max": heat_max, "availability": availability, "has_groups": has_groups,
            "requires_grouping": requires_grouping,
            "show_individual_charts": candidate_count <= MAX_INDIVIDUAL_CHART_PAGES,
            "individual_chart_limit": MAX_INDIVIDUAL_CHART_PAGES}


def insert_members(cursor, comparison_id, result_ids, group_label="Unassigned"):
    if not result_ids:
        return 0
    placeholders = ",".join(["%s"] * len(result_ids))
    cursor.execute("SELECT COUNT(*) AS total FROM comparison_members WHERE comparison_id=%s", (comparison_id,))
    existing = int(cursor.fetchone()["total"] or 0)
    if existing + len(result_ids) > MAX_COMPARISON_MEMBERS:
        raise ValueError("A comparison can contain at most 1,000 observations.")
    cursor.execute(f"""
        SELECT r.*, e.title AS experiment_title, e.semantic_provider, e.semantic_model,
               COALESCE(r.display_name, o.display_name, o.observation_key, r.url) AS member_name,
               CASE WHEN r.semantic_findings IS NULL THEN NULL ELSE JSON_LENGTH(r.semantic_findings) END AS finding_count
        FROM experiment_results r
        JOIN experiments e ON e.id=r.experiment_id
        LEFT JOIN dataset_observations o ON o.id=r.dataset_observation_id
        WHERE r.id IN ({placeholders}) AND r.status='completed'
    """, result_ids)
    rows_by_id = {int(row["id"]): row for row in cursor.fetchall()}
    added = 0
    for result_id in result_ids:
        row = rows_by_id.get(int(result_id))
        if not row:
            continue
        cursor.execute("SELECT id FROM comparison_members WHERE comparison_id=%s AND locator=%s LIMIT 1",
                       (comparison_id, row["url"]))
        if cursor.fetchone():
            continue
        cursor.execute("""
            INSERT IGNORE INTO comparison_members (
                comparison_id, source_result_id, source_experiment_id, source_experiment_title,
                locator, display_name, group_label, evaluated_at,
                axe_violations, axe_critical, axe_serious, axe_moderate, axe_minor,
                lighthouse_score, wave_errors, wave_contrast_errors, wave_alerts, wave_features, wave_aim_score,
                semantic_findings_count, semantic_risk_level, semantic_provider, semantic_model,
                semantic_total_tokens, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            comparison_id, row["id"], row["experiment_id"], row["experiment_title"],
            row["url"], str(row["member_name"])[:255], group_label,
            row.get("evaluated_at") or row.get("created_at"),
            row.get("axe_violations"), row.get("axe_critical"), row.get("axe_serious"),
            row.get("axe_moderate"), row.get("axe_minor"), row.get("lighthouse_score"),
            row.get("wave_errors") if row.get("wave_status") == "completed" else None,
            row.get("wave_contrast_errors") if row.get("wave_status") == "completed" else None,
            row.get("wave_alerts") if row.get("wave_status") == "completed" else None,
            row.get("wave_features") if row.get("wave_status") == "completed" else None,
            row.get("wave_aim_score"),
            row.get("finding_count") if row.get("semantic_status") == "completed" else None,
            row.get("semantic_risk_level") if row.get("semantic_status") == "completed" else None,
            row.get("semantic_provider"), row.get("semantic_model"),
            row.get("semantic_total_tokens") if row.get("semantic_status") == "completed" else None,
            now_local(),
        ))
        added += cursor.rowcount
        if cursor.rowcount and 'axe_wcag_violations' in row:
            metrics = {key: value for key, value in row.items() if key.startswith('axe_wcag_')}
            metrics['axe_best_practice_issues'] = row.get('axe_best_practice_issues')
            metrics['axe_combined_violations'] = row.get('axe_violations')
            persist_metrics(cursor, 'comparison_members', cursor.lastrowid, metrics)
    return added


def insert_remediation_members(cursor, comparison_id, run_ids, group_label="Unassigned"):
    if not run_ids:
        return 0
    placeholders=",".join(["%s"]*len(run_ids))
    cursor.execute("SELECT COUNT(*) AS total FROM comparison_members WHERE comparison_id=%s",(comparison_id,))
    existing=int(cursor.fetchone()["total"] or 0)
    if existing+len(run_ids)>MAX_COMPARISON_MEMBERS:
        raise ValueError("A comparison can contain at most 1,000 observations.")
    cursor.execute(f"""SELECT rr.id run_id,rr.accepted_iteration_id,ri.output_url,ri.candidate_key,
                               ri.axe_violations,ri.axe_wcag_violations,ri.axe_best_practice_issues,ri.axe_metrics_json,ri.lighthouse_score,ri.wave_aim_score,ri.created_at,
                               er.experiment_id source_experiment_id,e.title source_experiment_title,
                               COALESCE(er.display_name,o.display_name,o.observation_key,er.url) source_name
                        FROM remediation_runs rr
                        JOIN remediation_iterations ri ON ri.id=rr.accepted_iteration_id
                        JOIN experiment_results er ON er.id=rr.source_result_id
                        JOIN experiments e ON e.id=er.experiment_id
                        LEFT JOIN dataset_observations o ON o.id=er.dataset_observation_id
                        WHERE rr.id IN ({placeholders}) AND rr.status IN ('accepted','completed_with_warnings')""",run_ids)
    rows={int(row["run_id"]):row for row in cursor.fetchall()}; added=0
    for run_id in run_ids:
        row=rows.get(int(run_id))
        if not row: continue
        cursor.execute("SELECT id FROM comparison_members WHERE comparison_id=%s AND (source_remediation_run_id=%s OR locator=%s) LIMIT 1",(comparison_id,run_id,row["output_url"]))
        if cursor.fetchone(): continue
        suffix=(row.get("candidate_key") or str(run_id))[:8]
        cursor.execute("""INSERT INTO comparison_members (
            comparison_id,source_result_id,source_experiment_id,source_experiment_title,
            source_remediation_run_id,source_remediation_iteration_id,locator,display_name,
            group_label,evaluated_at,axe_violations,lighthouse_score,wave_aim_score,created_at
        ) VALUES (%s,NULL,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",(
            comparison_id,row["source_experiment_id"],row["source_experiment_title"],run_id,
            row["accepted_iteration_id"],row["output_url"],f"{row['source_name']} · remediated {suffix}"[:255],
            group_label,row["created_at"],row["axe_violations"],row["lighthouse_score"],row["wave_aim_score"],now_local()))
        added+=cursor.rowcount
        if cursor.rowcount and row.get('axe_wcag_violations') is not None:
            metrics = row.get('axe_metrics_json') or {}
            if isinstance(metrics, str): metrics = json.loads(metrics)
            metrics = {**metrics, 'axe_wcag_violations': row['axe_wcag_violations'],
                       'axe_best_practice_issues': row.get('axe_best_practice_issues'),
                       'axe_combined_violations': row.get('axe_violations')}
            persist_metrics(cursor, 'comparison_members', cursor.lastrowid, metrics)
    return added


def split_source_refs(values):
    result_ids=[]; run_ids=[]
    for value in dict.fromkeys(values):
        try: kind,identifier=value.split(":",1); identifier=int(identifier)
        except (AttributeError,TypeError,ValueError): continue
        if kind=="result": result_ids.append(identifier)
        elif kind=="remediation": run_ids.append(identifier)
    return result_ids,run_ids


@comparisons_bp.route("/comparisons", methods=["GET"])
def comparisons():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""SELECT c.*, COUNT(m.id) AS member_count FROM comparison_studies c
                      LEFT JOIN comparison_members m ON m.comparison_id=c.id
                      GROUP BY c.id ORDER BY c.updated_at DESC, c.id DESC""")
    studies = cursor.fetchall()
    cursor.execute("""SELECT e.id,e.title,e.source_type,COUNT(r.id) AS result_count
                      FROM experiments e LEFT JOIN experiment_results r ON r.experiment_id=e.id
                      WHERE e.status='completed' AND COALESCE(e.experiment_origin,'evaluation')<>'remediation'
                      GROUP BY e.id ORDER BY e.id DESC""")
    experiments = cursor.fetchall()
    cursor.execute("""SELECT rr.id,COALESCE(er.display_name,o.display_name,o.observation_key,er.url) title
                      FROM remediation_runs rr JOIN experiment_results er ON er.id=rr.source_result_id
                      LEFT JOIN dataset_observations o ON o.id=er.dataset_observation_id
                      WHERE rr.status IN ('accepted','completed_with_warnings') ORDER BY rr.completed_at DESC,rr.id DESC""")
    remediations=cursor.fetchall()
    sources=[{"ref":f"remediation:{row['id']}","kind":"remediation","id":row["id"],"title":row["title"],"result_count":1} for row in remediations]
    sources.extend({"ref":f"experiment:{row['id']}","kind":"experiment","id":row["id"],"title":row["title"],"result_count":row["result_count"]} for row in experiments)
    selected_source=request.args.get("source")
    valid_sources={row["ref"] for row in sources}
    if selected_source not in valid_sources: selected_source=sources[0]["ref"] if sources else None
    creating_new = request.args.get("new") == "1"
    comparison_id = None if creating_new else request.args.get("comparison_id", type=int)
    valid_comparison_ids = {row["id"] for row in studies}
    if not creating_new and comparison_id not in valid_comparison_ids:
        comparison_id = studies[0]["id"] if studies else None
    selected_comparison = next((row for row in studies if row["id"] == comparison_id), None)
    comparison_members = []
    if comparison_id:
        cursor.execute("""SELECT m.id,
                                  COALESCE(r.display_name,o.display_name,o.observation_key,m.display_name) AS display_name,
                                  m.locator,m.source_experiment_id,m.evaluated_at,
                                  m.axe_wcag_violations AS axe_violations,m.lighthouse_score,m.sort_order
                           FROM comparison_members m
                           LEFT JOIN experiment_results r ON r.id=m.source_result_id
                           LEFT JOIN dataset_observations o ON o.id=r.dataset_observation_id
                           WHERE m.comparison_id=%s ORDER BY m.sort_order,m.id""", (comparison_id,))
        comparison_members = cursor.fetchall()
    query = (request.args.get("q") or "").strip()
    results=[]
    if selected_source:
        source_kind,source_id=selected_source.split(":",1); source_id=int(source_id); like=f"%{query}%"
        if source_kind=="experiment":
            parameters=[comparison_id or 0,source_id]
            where="r.experiment_id=%s AND r.status='completed'"
            if query: where+=" AND (r.url LIKE %s OR r.display_name LIKE %s OR r.page_title LIKE %s)"; parameters.extend([like,like,like])
            cursor.execute(f"""SELECT r.id,r.url,r.axe_wcag_violations AS axe_violations,r.lighthouse_score,r.evaluated_at,e.source_type,
                CASE WHEN cm.id IS NULL THEN 0 ELSE 1 END already_added,
                COALESCE(r.display_name,o.display_name,o.observation_key,r.url) display_name
                FROM experiment_results r JOIN experiments e ON e.id=r.experiment_id
                LEFT JOIN dataset_observations o ON o.id=r.dataset_observation_id
                LEFT JOIN comparison_members cm ON cm.comparison_id=%s AND (cm.source_result_id=r.id OR cm.locator=r.url)
                WHERE {where} ORDER BY r.id""",parameters)
            results=cursor.fetchall()
            for row in results: row["source_ref"]=f"result:{row['id']}"; row["editable"]=True
        else:
            parameters=[comparison_id or 0,source_id]
            where="rr.id=%s AND rr.status IN ('accepted','completed_with_warnings')"
            if query: where+=" AND (er.url LIKE %s OR er.display_name LIKE %s OR er.page_title LIKE %s)"; parameters.extend([like,like,like])
            cursor.execute(f"""SELECT rr.id,ri.output_url url,ri.axe_wcag_violations AS axe_violations,ri.lighthouse_score,ri.created_at evaluated_at,
                'local_html' source_type,CASE WHEN cm.id IS NULL THEN 0 ELSE 1 END already_added,
                CONCAT(COALESCE(er.display_name,o.display_name,o.observation_key,er.url),' · remediated ',LEFT(COALESCE(ri.candidate_key,CAST(rr.id AS CHAR)),8)) display_name
                FROM remediation_runs rr JOIN remediation_iterations ri ON ri.id=rr.accepted_iteration_id
                JOIN experiment_results er ON er.id=rr.source_result_id LEFT JOIN dataset_observations o ON o.id=er.dataset_observation_id
                LEFT JOIN comparison_members cm ON cm.comparison_id=%s AND (cm.source_remediation_run_id=rr.id OR cm.locator=ri.output_url)
                WHERE {where}""",parameters)
            results=cursor.fetchall()
            for row in results: row["source_ref"]=f"remediation:{row['id']}"; row["editable"]=False
    cursor.close(); conn.close()
    return render_template("comparisons.html", studies=studies, sources=sources,
                           selected_source=selected_source, results=results, query=query,
                           selected_comparison=selected_comparison,
                           comparison_members=comparison_members,
                           new_comparison_title=_("New comparison %(timestamp)s", timestamp=now_local().strftime("%Y-%m-%d %H:%M:%S")))


@comparisons_bp.route("/comparisons/create", methods=["POST"])
def create_comparison():
    source_refs=request.form.getlist("source_ref") or [f"result:{value}" for value in request.form.getlist("result_id")]
    result_ids,run_ids=split_source_refs(source_refs)
    if not result_ids and not run_ids:
        flash(_("Select at least one completed result."), "warning")
        return redirect(url_for("comparisons.comparisons"))
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    try:
        comparison_id = request.form.get("comparison_id", type=int)
        if comparison_id:
            cursor.execute("SELECT id FROM comparison_studies WHERE id=%s", (comparison_id,))
            if not cursor.fetchone():
                raise ValueError("The selected comparison does not exist.")
        else:
            title = (request.form.get("title") or "").strip() or _(
                "New comparison %(timestamp)s", timestamp=now_local().strftime("%Y-%m-%d %H:%M:%S")
            )
            if len(title) > MAX_COMPARISON_NAME:
                raise ValueError(_("Comparison names can contain at most %(count)s characters.", count=MAX_COMPARISON_NAME))
            cursor.execute("""INSERT INTO comparison_studies
                (title,dimension_label,created_at,updated_at) VALUES (%s,'Group',%s,%s)""",
                (title, now_local(), now_local()))
            comparison_id = cursor.lastrowid
        batch_group = (request.form.get("batch_group") or "").strip()[:100]
        added=insert_members(cursor,comparison_id,result_ids,batch_group)
        added+=insert_remediation_members(cursor,comparison_id,run_ids,batch_group)
        cursor.execute("UPDATE comparison_studies SET updated_at=%s WHERE id=%s", (now_local(), comparison_id))
        conn.commit()
    except (ValueError, TypeError) as error:
        conn.rollback(); flash(_(str(error)), "danger")
        return redirect(url_for("comparisons.comparisons"))
    finally:
        cursor.close(); conn.close()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "comparison_id": comparison_id, "added": added})
    flash(_("%(count)s observation(s) added to the comparison.", count=added), "success")
    return redirect(url_for("comparisons.comparisons", comparison_id=comparison_id))


@comparisons_bp.route("/comparisons/<int:comparison_id>/members", methods=["POST"])
def add_comparison_members(comparison_id):
    payload = request.get_json(silent=True) or {}
    source_refs=payload.get("source_refs") or [f"result:{value}" for value in payload.get("result_ids") or []]
    conn = None; cursor = None
    try:
        result_ids,run_ids=split_source_refs(source_refs)
        conn = get_connection(); cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM comparison_studies WHERE id=%s", (comparison_id,))
        if not cursor.fetchone():
            raise ValueError(_("The comparison does not exist."))
        added = insert_members(cursor, comparison_id, result_ids, str(payload.get("group") or "")[:MAX_GROUP_LABEL])
        added += insert_remediation_members(cursor, comparison_id, run_ids, str(payload.get("group") or "")[:MAX_GROUP_LABEL])
        cursor.execute("UPDATE comparison_studies SET updated_at=%s WHERE id=%s", (now_local(), comparison_id))
        conn.commit()
    except (TypeError, ValueError) as error:
        if conn:
            conn.rollback()
        return jsonify({"ok": False, "error": str(error)}), 400
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return jsonify({"ok": True, "added": added})


@comparisons_bp.route("/comparisons/<int:comparison_id>", methods=["GET"])
def comparison_detail(comparison_id):
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM comparison_studies WHERE id=%s", (comparison_id,))
    study = cursor.fetchone()
    if not study:
        cursor.close(); conn.close(); flash(_("The comparison does not exist."), "warning")
        return redirect(url_for("comparisons.comparisons"))
    cursor.execute("""SELECT m.*,
                             COALESCE(r.display_name,o.display_name,o.observation_key,m.display_name) AS display_name
                      FROM comparison_members m
                      LEFT JOIN experiment_results r ON r.id=m.source_result_id
                      LEFT JOIN dataset_observations o ON o.id=r.dataset_observation_id
                      WHERE m.comparison_id=%s ORDER BY m.sort_order,m.id""", (comparison_id,))
    members = [project_wcag(row) for row in cursor.fetchall()]; cursor.close(); conn.close()
    analysis = comparison_analysis(members)
    return render_template("comparison_detail.html", study=study, members=members, analysis=analysis,
                           chart_data=json.dumps(analysis["summaries"]),
                           cohort_data=json.dumps(analysis["cohort_summary"]),
                           cohort_conditions=json.dumps(analysis["cohort_conditions"]),
                           box_data=json.dumps(analysis["improvement_boxes"]),
                           delta_data=json.dumps(analysis["deltas"]),
                           member_data=json.dumps([{key: row.get(key) for key in (
                               "id", "display_name", "group_label", "group_label_2", "is_baseline",
                               "axe_violations", "lighthouse_score", "wave_errors",
                               "wave_contrast_errors", "wave_alerts", "wave_features",
                               "semantic_findings_count", "semantic_total_tokens", "semantic_model")}
                               for row in members]))


@comparisons_bp.route("/comparisons/<int:comparison_id>/update", methods=["POST"])
def update_comparison(comparison_id):
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    try:
        title = (request.form.get("title") or "").strip()
        dimension = (request.form.get("dimension_label") or "Group").strip()[:100]
        notes = (request.form.get("notes") or "").strip()
        if not title:
            raise ValueError("Comparison title is required.")
        if len(title) > MAX_COMPARISON_NAME:
            raise ValueError(_("Comparison names can contain at most %(count)s characters.", count=MAX_COMPARISON_NAME))
        cursor.execute("UPDATE comparison_studies SET title=%s,dimension_label=%s,notes=%s,updated_at=%s WHERE id=%s",
                       (title, dimension, notes, now_local(), comparison_id))
        cursor.execute("SELECT id FROM comparison_members WHERE comparison_id=%s", (comparison_id,))
        valid_ids = {row["id"] for row in cursor.fetchall()}
        for member_id in valid_ids:
            name = (request.form.get(f"name_{member_id}") or "").strip()[:255]
            group = (request.form.get(f"group_{member_id}") or "").strip()[:100]
            pair = (request.form.get(f"pair_{member_id}") or "").strip()[:255]
            baseline = request.form.get(f"baseline_{member_id}") == "on"
            if not name:
                raise ValueError("Every observation needs a name.")
            cursor.execute("""UPDATE comparison_members SET display_name=%s,group_label=%s,pair_key=%s,is_baseline=%s
                              WHERE id=%s AND comparison_id=%s""",
                           (name, group, pair or None, baseline, member_id, comparison_id))
        conn.commit()
    except ValueError as error:
        conn.rollback(); flash(_(str(error)), "danger")
    finally:
        cursor.close(); conn.close()
    return redirect(url_for("comparisons.comparison_detail", comparison_id=comparison_id))


@comparisons_bp.route("/comparisons/<int:comparison_id>/settings", methods=["POST"])
def update_comparison_setting(comparison_id):
    payload = request.get_json(silent=True) or {}
    field = payload.get("field")
    limits = {"title": (MAX_COMPARISON_NAME, False), "notes": (2000, True)}
    if field not in limits:
        return jsonify({"ok": False, "error": _("This field cannot be edited.")}), 400
    limit, allow_empty = limits[field]
    value = str(payload.get("value") or "").strip()
    if (not value and not allow_empty) or len(value) > limit:
        return jsonify({"ok": False, "error": _("The value is not valid.")}), 400
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute(f"UPDATE comparison_studies SET {field}=%s,updated_at=%s WHERE id=%s",
                   (value or None, now_local(), comparison_id))
    conn.commit(); cursor.close(); conn.close()
    return jsonify({"ok": True, "value": value})


@comparisons_bp.route("/comparisons/<int:comparison_id>/members/<int:member_id>/delete", methods=["POST"])
def delete_comparison_member(comparison_id, member_id):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("DELETE FROM comparison_members WHERE id=%s AND comparison_id=%s", (member_id, comparison_id))
    cursor.execute("UPDATE comparison_studies SET updated_at=%s WHERE id=%s", (now_local(), comparison_id))
    conn.commit(); cursor.close(); conn.close()
    return redirect(url_for("comparisons.comparison_detail", comparison_id=comparison_id))


@comparisons_bp.route("/comparisons/<int:comparison_id>/members/delete", methods=["POST"])
def delete_comparison_members(comparison_id):
    member_ids = [int(value) for value in request.form.getlist("member_id") if value.isdigit()]
    if member_ids:
        placeholders = ",".join(["%s"] * len(member_ids))
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(f"DELETE FROM comparison_members WHERE comparison_id=%s AND id IN ({placeholders})",
                       [comparison_id, *member_ids])
        cursor.execute("UPDATE comparison_studies SET updated_at=%s WHERE id=%s", (now_local(), comparison_id))
        conn.commit(); cursor.close(); conn.close()
    return redirect(url_for("comparisons.comparisons", comparison_id=comparison_id,
                            source=request.form.get("source", "")))


@comparisons_bp.route("/comparisons/<int:comparison_id>/members/<int:member_id>", methods=["POST"])
def update_comparison_member(comparison_id, member_id):
    payload = request.get_json(silent=True) or {}
    field = payload.get("field")
    definitions = {
        "display_name": (MAX_OBSERVATION_NAME, False),
        "group_label": (MAX_GROUP_LABEL, True),
        "group_label_2": (MAX_GROUP_LABEL, True),
        "pair_key": (MAX_PAIR_KEY, True),
    }
    if field not in definitions:
        return jsonify({"ok": False, "error": _("This field cannot be edited.")}), 400
    limit, allow_empty = definitions[field]
    value = str(payload.get("value") or "").strip()
    if (not value and not allow_empty) or len(value) > limit:
        return jsonify({"ok": False, "error": _("Use between 1 and %(count)s characters.", count=limit)}), 400
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("""SELECT m.id,m.source_result_id,r.normalized_url
                      FROM comparison_members m
                      LEFT JOIN experiment_results r ON r.id=m.source_result_id
                      WHERE m.id=%s AND m.comparison_id=%s""", (member_id, comparison_id))
    member = cursor.fetchone()
    if not member:
        cursor.close(); conn.close()
        return jsonify({"ok": False, "error": _("The observation does not exist.")}), 404
    stored_value = value if field in {"group_label", "group_label_2"} else value or None
    if field == "display_name" and member.get("source_result_id"):
        if member.get("normalized_url"):
            cursor.execute("UPDATE experiment_results SET display_name=%s WHERE normalized_url=%s",
                           (stored_value, member["normalized_url"]))
            cursor.execute("""UPDATE comparison_members m JOIN experiment_results r ON r.id=m.source_result_id
                              SET m.display_name=%s WHERE r.normalized_url=%s""",
                           (stored_value, member["normalized_url"]))
        else:
            cursor.execute("UPDATE experiment_results SET display_name=%s WHERE id=%s", (stored_value, member["source_result_id"]))
            cursor.execute("UPDATE comparison_members SET display_name=%s WHERE source_result_id=%s",
                           (stored_value, member["source_result_id"]))
    else:
        cursor.execute(f"UPDATE comparison_members SET {field}=%s WHERE id=%s AND comparison_id=%s",
                       (stored_value, member_id, comparison_id))
    conn.commit(); cursor.close(); conn.close()
    return jsonify({"ok": True, "value": value})


@comparisons_bp.route("/comparisons/<int:comparison_id>/baseline", methods=["POST"])
def update_comparison_baseline(comparison_id):
    member_id = (request.get_json(silent=True) or {}).get("member_id")
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id,pair_key FROM comparison_members WHERE comparison_id=%s AND id=%s", (comparison_id, member_id))
    member = cursor.fetchone()
    if not member:
        cursor.close(); conn.close()
        return jsonify({"ok": False, "error": _("The page does not exist in this comparison.")}), 404
    if (member.get("pair_key") or "").strip():
        cursor.execute("UPDATE comparison_members SET is_baseline=FALSE WHERE comparison_id=%s AND pair_key=%s",
                       (comparison_id, member["pair_key"]))
    else:
        cursor.execute("UPDATE comparison_members SET is_baseline=FALSE WHERE comparison_id=%s", (comparison_id,))
    cursor.execute("UPDATE comparison_members SET is_baseline=TRUE WHERE comparison_id=%s AND id=%s", (comparison_id, member_id))
    conn.commit(); cursor.close(); conn.close()
    return jsonify({"ok": True})


@comparisons_bp.route("/comparisons/<int:comparison_id>/order", methods=["POST"])
def update_comparison_order(comparison_id):
    member_ids = (request.get_json(silent=True) or {}).get("member_ids") or []
    conn = get_connection(); cursor = conn.cursor()
    for position, member_id in enumerate(member_ids):
        cursor.execute("UPDATE comparison_members SET sort_order=%s WHERE comparison_id=%s AND id=%s",
                       (position, comparison_id, member_id))
    conn.commit(); cursor.close(); conn.close()
    return jsonify({"ok": True})


@comparisons_bp.route("/comparisons/<int:comparison_id>/delete", methods=["POST"])
def delete_comparison(comparison_id):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("DELETE FROM comparison_studies WHERE id=%s", (comparison_id,))
    conn.commit(); cursor.close(); conn.close()
    flash(_("Comparison deleted."), "success")
    return redirect(url_for("comparisons.comparisons"))


@comparisons_bp.route("/results/<int:result_id>/display-name", methods=["POST"])
def rename_result(result_id):
    payload = request.get_json(silent=True) or request.form
    display_name = (payload.get("display_name") or "").strip()
    if not display_name or len(display_name) > MAX_OBSERVATION_NAME:
        return jsonify({"ok": False, "error": _("Use a name between 1 and %(count)s characters.", count=MAX_OBSERVATION_NAME)}), 400
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id,normalized_url FROM experiment_results WHERE id=%s", (result_id,))
    result = cursor.fetchone()
    if not result:
        cursor.close(); conn.close()
        return jsonify({"ok": False, "error": _("The observation does not exist.")}), 404
    if result.get("normalized_url"):
        cursor.execute("UPDATE experiment_results SET display_name=%s WHERE normalized_url=%s",
                       (display_name, result["normalized_url"]))
        cursor.execute("""UPDATE comparison_members m JOIN experiment_results r ON r.id=m.source_result_id
                          SET m.display_name=%s WHERE r.normalized_url=%s""",
                       (display_name, result["normalized_url"]))
    else:
        cursor.execute("UPDATE experiment_results SET display_name=%s WHERE id=%s", (display_name, result_id))
        cursor.execute("UPDATE comparison_members SET display_name=%s WHERE source_result_id=%s", (display_name, result_id))
    conn.commit(); cursor.close(); conn.close()
    return jsonify({"ok": True, "display_name": display_name})
