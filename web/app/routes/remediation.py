import os
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Blueprint, Response, flash, redirect, render_template, request, send_file, url_for
from flask_babel import gettext as _

from database import get_connection
from remediation_rag import status as rag_status
from settings import get_settings
from remediation_recipes import automatic_recipe, common_conditions
from remediation_model_choices import model_choices, model_choice, frozen_model_configuration
from remediation_approaches import presentation_priority, presentation_name


remediation_bp = Blueprint("remediation", __name__, url_prefix="/remediation")
DATASET_ROOT = Path(os.getenv("DATASET_ROOT", "/datasets"))
PAGE_TYPES = ("homepage", "form", "search", "article", "product", "authentication", "listing", "media")
def available_llm_options(settings=None):
    settings = settings or get_settings()
    return model_choices(settings) if settings.get("openrouter_api_key") and settings.get("openrouter_base_url") else []



def now_local():
    return datetime.now(ZoneInfo(get_settings()["app_timezone"])).replace(tzinfo=None)


def source_snapshot(row):
    if row.get("response_source_path") and Path(row["response_source_path"]).is_file():
        return row["response_source_path"]
    if row.get("source_snapshot_path") and Path(row["source_snapshot_path"]).is_file():
        return row["source_snapshot_path"]
    if row.get("storage_key") and row.get("relative_path"):
        path = DATASET_ROOT / row["storage_key"] / row["relative_path"]
        if path.is_file():
            return str(path)
    return None


def improvement_metrics(original_axe, remediated_axe, original_lighthouse, remediated_lighthouse):
    """Return comparable percentage outcomes without hiding each metric's scale."""
    axe_percent=None
    if original_axe is not None and remediated_axe is not None:
        original=float(original_axe); remediated=float(remediated_axe)
        axe_percent=(100.0*(original-remediated)/original) if original else (0.0 if remediated == 0 else None)
    lighthouse_points=None; lighthouse_headroom=None
    if original_lighthouse is not None and remediated_lighthouse is not None:
        original=float(original_lighthouse); remediated=float(remediated_lighthouse)
        lighthouse_points=remediated-original
        lighthouse_headroom=(100.0*lighthouse_points/(100.0-original)) if original < 100 else (0.0 if lighthouse_points == 0 else None)
    return {"axe_percent":axe_percent,"lighthouse_points":lighthouse_points,"lighthouse_headroom_percent":lighthouse_headroom}


def global_lighthouse_metrics(rows):
    """Aggregate every terminal run that produced a candidate evaluation."""
    pairs=[(float(row["original_lighthouse"]),float(row["result_lighthouse"])) for row in rows if row.get("original_lighthouse") is not None and row.get("result_lighthouse") is not None]
    headroom=sum(100-original for original,_ in pairs)
    gain=sum(result-original for original,result in pairs)
    return {
        "headroom_percent":100*gain/headroom if headroom else (0.0 if pairs and gain == 0 else None),
        "average_gain":sum(result-original for original,result in pairs)/len(pairs) if pairs else None,
    }

def page_type_signals(snapshot_path):
    content=Path(snapshot_path).read_text(encoding="utf-8",errors="replace").lower()
    scores={"form":len(re.findall(r"<(form|input|select|textarea)\b",content)),"search":len(re.findall(r"(type=[\"']search|role=[\"']search|<search\b)",content))*3,"article":len(re.findall(r"<(article|time)\b",content))*2,"product":len(re.findall(r"(add.to.cart|itemprop=[\"']price|product)",content)),"authentication":len(re.findall(r"(type=[\"']password|autocomplete=[\"'](current-password|username))",content))*3,"listing":len(re.findall(r"(<ol\b|pagination|filter)",content)),"media":len(re.findall(r"<(video|audio|track)\b",content))*3,"homepage":len(re.findall(r"<(nav|header|footer)\b",content))}
    # Specific interaction/page-purpose signals are more diagnostic than generic
    # elements such as forms or timestamps. This avoids classifying a search page
    # as an article merely because its results contain several <time> elements.
    if scores["authentication"]:
        page_type="authentication"
    elif scores["search"]:
        page_type="search"
    elif scores["product"] >= 2:
        page_type="product"
    elif scores["media"]:
        page_type="media"
    elif scores["listing"] >= 2:
        page_type="listing"
    elif scores["homepage"] >= 3:
        page_type="homepage"
    elif scores["form"] >= 3:
        page_type="form"
    elif scores["article"] >= 2:
        page_type="article"
    else:
        page_type="homepage"
    return page_type,scores,content


def classified_page_type(snapshot_path):
    return page_type_signals(snapshot_path)[0]


@remediation_bp.get("/templates")
def templates():
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM remediation_templates ORDER BY is_builtin DESC,page_type,name")
    rows = cursor.fetchall(); cursor.close(); conn.close()
    return render_template("remediation_templates.html", templates=rows, page_types=PAGE_TYPES)


@remediation_bp.post("/templates")
def upload_template():
    upload = request.files.get("html_file")
    if not upload or not upload.filename.lower().endswith((".html", ".htm")):
        flash(_("Choose an HTML template file."), "danger"); return redirect(url_for("remediation.templates"))
    content = upload.read().decode("utf-8", errors="strict")
    if "<html" not in content.lower() or len(content) > 2_000_000:
        flash(_("The template must be a complete HTML document under 2 MB."), "danger"); return redirect(url_for("remediation.templates"))
    conn = get_connection(); cursor = conn.cursor()
    page_type=request.form.get("page_type", "homepage")
    if page_type not in PAGE_TYPES: page_type="homepage"
    cursor.execute("INSERT INTO remediation_templates (name,page_type,description,html_template,is_builtin,created_at,updated_at) VALUES (%s,%s,%s,%s,FALSE,%s,%s)",
                   ((request.form.get("name") or upload.filename)[:160], page_type, request.form.get("description", "")[:2000], content, now_local(), now_local()))
    conn.commit(); cursor.close(); conn.close(); flash(_("Template added to the catalog."), "success")
    return redirect(url_for("remediation.templates"))


@remediation_bp.post("/templates/<int:template_id>/delete")
def delete_template(template_id):
    conn=get_connection(); cursor=conn.cursor(); cursor.execute("DELETE FROM remediation_templates WHERE id=%s AND is_builtin=FALSE", (template_id,)); conn.commit(); cursor.close(); conn.close()
    return redirect(url_for("remediation.templates"))


@remediation_bp.get("/")
def runs():
    conn=get_connection(); cursor=conn.cursor(dictionary=True)
    cursor.execute("""SELECT rr.*,
        CASE WHEN e.source_type='local_html' THEN COALESCE(r.display_name,o.display_name,o.observation_key)
             ELSE COALESCE(r.display_name,r.captured_url,r.url) END source_name,
        r.axe_violations original_axe,r.lighthouse_score original_lighthouse,r.wave_aim_score original_aim,
        accepted.axe_violations remediated_axe,
        accepted.lighthouse_score remediated_lighthouse,
        accepted.wave_aim_score remediated_aim,
        accepted.dom_distance remediated_dom_distance,
        accepted.strategy_json accepted_strategy_json,
        latest.axe_violations latest_axe,
        latest.lighthouse_score latest_lighthouse,
        latest.wave_aim_score latest_aim,
        latest.dom_distance latest_dom_distance,
        latest.generator_model actual_generator_model,
        latest.strategy_json latest_strategy_json,
        r.evaluated_at source_evaluated_at,e.title source_experiment,e.source_type,
        EXISTS(SELECT 1 FROM remediation_iterations rag_iteration WHERE rag_iteration.run_id=rr.id
            AND JSON_LENGTH(JSON_EXTRACT(rag_iteration.strategy_json,'$.rag.retrieved')) > 0) rag_used,
        (SELECT re.actor FROM remediation_events re WHERE re.run_id=rr.id ORDER BY re.id DESC LIMIT 1) latest_actor
        FROM remediation_runs rr JOIN experiment_results r ON r.id=rr.source_result_id
        JOIN experiments e ON e.id=r.experiment_id
        LEFT JOIN dataset_observations o ON o.id=r.dataset_observation_id
        LEFT JOIN remediation_iterations accepted ON accepted.id=rr.accepted_iteration_id
        LEFT JOIN remediation_iterations latest ON latest.id=(SELECT ri.id FROM remediation_iterations ri WHERE ri.run_id=rr.id ORDER BY (GREATEST(COALESCE(ri.axe_violations,999999)-rr.max_axe,0)+GREATEST(rr.min_lighthouse-COALESCE(ri.lighthouse_score,0),0)) ASC,ri.iteration_number ASC LIMIT 1)
        ORDER BY rr.id DESC""")
    histories=cursor.fetchall()
    cursor.execute("SELECT run_id,generator_model,reviewer_model,agent_usage_json FROM remediation_iterations ORDER BY run_id,iteration_number")
    participation={}
    policies={row['id']:row.get('review_policy') for row in histories}
    for iteration in cursor.fetchall():
        roles=participation.setdefault(iteration['run_id'],{})
        try: usage=json.loads(iteration.get('agent_usage_json') or '[]')
        except (ValueError,TypeError): usage=[]
        if not isinstance(usage,list): usage=[]
        if not usage:
            usage=[{'model':iteration.get('generator_model'),'role':'Generator'}]
            if policies.get(iteration['run_id']) != 'automated':
                usage.append({'model':iteration.get('reviewer_model'),'role':'Coordinator'})
        for entry in usage:
            if not isinstance(entry,dict): continue
            model=entry.get('model')
            if model and not model.startswith('system/'):
                roles.setdefault(model,set()).add(entry.get('role') or 'Agent')
    for row in histories:
        row['participants']=[]
        try:
            recorded=json.loads(row.get('accepted_strategy_json') or row.get('latest_strategy_json') or '{}')
            row['presentation_priority']=presentation_priority(row.get('accessibility_priority'),recorded)
            row['presentation_name']=presentation_name(row.get('accessibility_priority'),recorded)
        except (ValueError,TypeError):
            row['presentation_priority']=row.get('accessibility_priority')
        for model,roles in participation.get(row['id'],{}).items():
            concise_roles=set()
            for role in roles:
                if 'reconstruction' in role.lower():
                    concise_roles.add(_('Reconstruction agent'))
                elif 'architecture' in role.lower() or 'planning' in role.lower():
                    concise_roles.add(_('Architecture planning specialist'))
                else:
                    concise_roles.add(_(role.split(' · ',1)[0]))
            row['participants'].append({'model':model,'roles':', '.join(sorted(concise_roles))})
    cursor.close(); conn.close()
    completed=[row for row in histories if row["status"] not in {"queued","running"}]
    accepted=[row for row in histories if row["status"] in {"accepted","completed_with_warnings"}]
    for row in histories:
        row["result_axe"]=row.get("remediated_axe") if row["status"] in {"accepted","completed_with_warnings"} else row.get("latest_axe")
        row["result_lighthouse"]=row.get("remediated_lighthouse") if row["status"] in {"accepted","completed_with_warnings"} else row.get("latest_lighthouse")
        row["result_aim"]=row.get("remediated_aim") if row["status"] in {"accepted","completed_with_warnings"} else row.get("latest_aim")
        row["improvement"]=improvement_metrics(row.get("original_axe"),row.get("result_axe"),row.get("original_lighthouse"),row.get("result_lighthouse"))
    axe_pairs=[(float(row["original_axe"]),float(row["remediated_axe"])) for row in accepted if row["original_axe"] is not None and row["remediated_axe"] is not None]
    lighthouse_summary=global_lighthouse_metrics(completed)
    aim_gains=[float(row["remediated_aim"])-float(row["original_aim"]) for row in accepted if row.get("original_aim") is not None and row["remediated_aim"] is not None]
    dom_values=[float(row["remediated_dom_distance"]) for row in accepted if row.get("remediated_dom_distance") is not None]
    retention=[]
    for row in accepted:
        try: retention.append(float((json.loads(row.get("accepted_strategy_json") or "{}").get("content_retention") or {}).get("text_percent")))
        except (ValueError,TypeError,AttributeError): pass
    axe_original=sum(pair[0] for pair in axe_pairs)
    axe_remediated=sum(pair[1] for pair in axe_pairs)
    summary={"total":len(histories),"active":sum(row["status"] in {"queued","running"} for row in histories),"accepted":len(accepted),"completed":len(completed),"cost":sum(float(row["total_cost_usd"] or 0) for row in histories),"axe_original_total":axe_original,"axe_remediated_total":axe_remediated,"axe_removed_total":axe_original-axe_remediated,"axe_improvement_percent":100*(axe_original-axe_remediated)/axe_original if axe_original else None,"lighthouse_headroom_percent":lighthouse_summary["headroom_percent"],"average_lighthouse_gain":lighthouse_summary["average_gain"],"average_aim_gain":sum(aim_gains)/len(aim_gains) if aim_gains else None,"average_dom":sum(dom_values)/len(dom_values) if dom_values else None,"average_retention":sum(retention)/len(retention) if retention else None}
    return render_template("remediation_history.html", runs=histories, summary=summary, has_active=bool(summary["active"]))


@remediation_bp.post("/<int:run_id>/delete")
def delete_run(run_id):
    conn=get_connection(); cursor=conn.cursor(dictionary=True)
    cursor.execute("SELECT id,status,published_experiment_id FROM remediation_runs WHERE id=%s",(run_id,)); run=cursor.fetchone()
    if not run:
        cursor.close(); conn.close(); flash(_("The requested remediation run does not exist."),"warning"); return redirect(url_for("remediation.runs"))
    if run["status"] in {"queued","running"}:
        cursor.close(); conn.close(); flash(_("A queued or running remediation cannot be deleted."),"warning"); return redirect(url_for("remediation.runs"))
    cursor.execute("SELECT COUNT(*) total FROM comparison_members WHERE source_remediation_run_id=%s",(run_id,))
    comparison_count=int((cursor.fetchone() or {}).get("total") or 0)
    if comparison_count:
        cursor.close(); conn.close(); flash(_("This remediation is used by %(count)s comparison(s). Remove it from those comparisons before deleting the run.",count=comparison_count),"warning"); return redirect(url_for("remediation.runs"))
    published_id=run.get("published_experiment_id")
    if published_id:
        cursor.execute("""SELECT COUNT(*) total FROM remediation_runs rr JOIN experiment_results er ON er.id=rr.source_result_id WHERE rr.id<>%s AND er.experiment_id=%s""",(run_id,published_id))
        if int((cursor.fetchone() or {}).get("total") or 0):
            cursor.close(); conn.close(); flash(_("This result is the source of another remediation run and cannot be deleted."),"warning"); return redirect(url_for("remediation.runs"))
    cursor.execute("SELECT output_path,screenshot_path FROM remediation_iterations WHERE run_id=%s",(run_id,)); artifacts=cursor.fetchall()
    try:
        cursor.execute("DELETE FROM remediation_runs WHERE id=%s",(run_id,))
        if published_id:
            cursor.execute("DELETE FROM experiment_results WHERE experiment_id=%s",(published_id,))
            cursor.execute("DELETE FROM experiment_environment WHERE experiment_id=%s",(published_id,))
            cursor.execute("DELETE FROM experiments WHERE id=%s",(published_id,))
        conn.commit()
    except Exception:
        conn.rollback(); cursor.close(); conn.close(); flash(_("The remediation run could not be deleted."),"danger"); return redirect(url_for("remediation.runs"))
    cursor.close(); conn.close()
    dataset_root=(DATASET_ROOT/"remediations").resolve(); run_directory=(dataset_root/str(run_id)).resolve()
    if dataset_root in run_directory.parents and run_directory.is_dir(): shutil.rmtree(run_directory,ignore_errors=True)
    results_root=Path("/results/raw").resolve()
    directories=set()
    for item in artifacts:
        screenshot=Path(item["screenshot_path"]).resolve() if item.get("screenshot_path") else None
        if screenshot and results_root in screenshot.parents and screenshot.parent.name.startswith(f"experiment_remediation_{run_id}_"): directories.add(screenshot.parent)
    if published_id: directories.add(results_root/f"experiment_{published_id}")
    for directory in directories:
        resolved=directory.resolve()
        if results_root in resolved.parents and resolved.is_dir(): shutil.rmtree(resolved,ignore_errors=True)
    flash(_("Remediation run and its generated evidence were deleted."),"success")
    return redirect(url_for("remediation.runs"))


@remediation_bp.route("/new", methods=["GET", "POST"])
def new_run():
    settings=get_settings(); options=available_llm_options(settings)
    conn=get_connection(); cursor=conn.cursor(dictionary=True)
    if request.method == "POST":
        result_id=request.form.get("source_result_id", type=int); template_id=None
        cursor.execute("""SELECT r.*,d.storage_key,o.relative_path FROM experiment_results r LEFT JOIN dataset_observations o ON o.id=r.dataset_observation_id LEFT JOIN datasets d ON d.id=o.dataset_id WHERE r.id=%s AND r.status='completed'""", (result_id,))
        source=cursor.fetchone()
        if not source or not source_snapshot(source):
            cursor.close(); conn.close(); flash(_("This legacy acquisition has no stored HTML snapshot and cannot be remediated reproducibly."), "danger"); return redirect(url_for("remediation.new_run"))
        preservation_levels={0:15,1:35,2:55,3:75,4:90}
        requested_level=request.form.get("preservation_level",type=int)
        priority=preservation_levels.get(requested_level,max(0,min(100,request.form.get("accessibility_priority",type=int) or 55)))
        expert=request.form.get("use_expert_settings")=="on"
        execution_mode=request.form.get('execution_mode','iterative')
        if execution_mode not in {'iterative','single_shot','regenerate_only','regenerate_refine'}: execution_mode='iterative'
        if priority>=75 and execution_mode=='iterative': execution_mode='regenerate_refine'
        selection="component_knowledge"; rationale="No page template is used. Relevant accessible framework components are retrieved from the acquired page inventory."
        requested_format=request.form.get("transformation_format","html") if expert else "auto"
        if requested_format not in {"auto","html","markdown"}: requested_format="auto"
        page_type=classified_page_type(source_snapshot(source))
        representation=("markdown" if priority>=80 else "html") if requested_format=="auto" else requested_format
        recipe=automatic_recipe(priority,execution_mode,settings=settings)
        requested_temperature=request.form.get("temperature",type=float)
        temperature=max(0,min(1,requested_temperature if requested_temperature is not None else recipe["temperature"])) if expert else recipe["temperature"]
        selected_model=request.form.get('selected_model','')
        try:
            choice=model_choice(selected_model, settings)
        except ValueError:
            cursor.close(); conn.close(); flash(_('Choose a model from the configured slider.'),'danger')
            return redirect(url_for('remediation.new_run'))
        mode='user'; tier=choice['tier']
        generator_model=reviewer_model=choice['model']
        provider=reviewer=generator_model.split('/',1)[0]
        maximum=max(1,min(10,request.form.get("max_iterations",type=int) or recipe["iterations"])) if expert else recipe["iterations"]
        review_policy='automated'  # LLM diagnosis guides patches, never acceptance.
        title=(request.form.get("title") or f"Remediation of {source.get('display_name') or source['url']}")[:180]
        # WAVE remains available for separate evaluations, never for the loop.
        use_wave=False
        # ACT is the default adaptive aid; researchers can explicitly disable it.
        # Record it as armed even if the service is unavailable; empty retrieval
        # must not fabricate advice or prevent retaining an evaluated candidate.
        act_default='off' if request.form.get('act_grounding_configured')=='1' else 'on'
        use_rag=request.form.get('act_grounding',act_default) != 'off'
        if execution_mode=='single_shot':
            maximum=1; review_policy='automated'; use_rag=False; representation='html'
        if execution_mode in {'regenerate_only','regenerate_refine'}:
            if not expert or requested_temperature is None: temperature=.5
            review_policy='automated'
            if execution_mode=='regenerate_only': maximum=1; use_rag=False
            design_base=request.form.get('regeneration_framework','bootstrap')
            if design_base not in {'bootstrap','pico','bulma'}:
                cursor.close(); conn.close(); flash(_('Choose a supported design base.'),'danger'); return redirect(url_for('remediation.new_run'))
            selection={'bootstrap':'vera_reference','pico':'pico_reference','bulma':'bulma_reference'}[design_base]
            rationale='Mandatory '+design_base+' design base with page-type reference; later iterations use localized patches.'
        rag_top_k=max(2,min(12,request.form.get("rag_top_k",type=int) or recipe["rag_top_k"])) if expert else recipe["rag_top_k"]
        max_cost=max(0.01,min(100,request.form.get("max_cost_usd",type=float) or recipe["cost"])) if expert else recipe["cost"]
        max_seconds=max(30,min(7200,request.form.get("max_execution_seconds",type=int) or recipe["seconds"])) if expert else recipe["seconds"]
        min_lighthouse=max(0,min(100,request.form.get("min_lighthouse",type=int) if request.form.get("min_lighthouse") is not None else recipe["lighthouse"])) if expert else recipe["lighthouse"]
        max_axe=max(0,request.form.get("max_axe",type=int) if request.form.get("max_axe") is not None else recipe["axe"]) if expert else recipe["axe"]
        min_aim=None  # No paid WAVE criterion in remediation.
        cursor.execute("""INSERT INTO remediation_runs (source_result_id,template_id,title,transformation_format,generator_provider,generator_model,reviewer_provider,reviewer_model,max_iterations,min_lighthouse,max_axe,min_aim,status,created_at,accessibility_priority,temperature,template_selection,template_rationale,use_wave,model_selection_mode,model_cost_tier,allowed_models_json,max_dom_distance,enforce_dom_distance,review_policy,max_cost_usd,max_execution_seconds,use_rag,rag_top_k) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'queued',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
          (result_id,template_id,title,representation,provider,generator_model,reviewer,reviewer_model,maximum,min_lighthouse,max_axe,min_aim if use_wave else None,now_local(),priority,temperature,selection,rationale,use_wave,mode,tier,json.dumps([generator_model]),priority,False,review_policy,max_cost,max_seconds,use_rag,rag_top_k))
        run_id=cursor.lastrowid
        cursor.execute('UPDATE remediation_runs SET model_config_json=%s WHERE id=%s',(json.dumps(frozen_model_configuration(choice)),run_id))
        cursor.execute('UPDATE remediation_runs SET use_expert_settings=%s WHERE id=%s',(expert,run_id))
        if generator_model.startswith('ollama/'):
            from local_llm import local_configuration
            cursor.execute('UPDATE remediation_runs SET local_llm_config_json=%s WHERE id=%s',
                           (json.dumps(local_configuration(settings)), run_id))
        cursor.execute('UPDATE remediation_runs SET execution_mode=%s WHERE id=%s',(execution_mode,run_id))
        evidence_mode=request.form.get("generator_evidence_mode","guided") if expert else "guided"
        if evidence_mode not in {"guided","localized","independent"}: evidence_mode="guided"
        cursor.execute("UPDATE remediation_runs SET generator_evidence_mode=%s WHERE id=%s",(evidence_mode,run_id))
        reconstruction_mode=request.form.get("reconstruction_mode","whole_page") if expert else "whole_page"
        if reconstruction_mode not in {"whole_page","fragmented"}: reconstruction_mode="whole_page"
        cursor.execute("UPDATE remediation_runs SET reconstruction_mode=%s WHERE id=%s",(reconstruction_mode,run_id))
        markdown_provider=request.form.get("markdown_provider","local") if expert else "local"
        if markdown_provider not in {"local","jina"}: markdown_provider="local"
        cursor.execute("UPDATE remediation_runs SET markdown_provider=%s WHERE id=%s",(markdown_provider,run_id))
        conn.commit(); cursor.close(); conn.close(); return redirect(url_for("remediation.run_detail",run_id=run_id))
    cursor.execute("""SELECT r.id,r.normalized_url,CASE WHEN e.source_type='local_html' THEN COALESCE(r.display_name,o.observation_key) ELSE COALESCE(r.captured_url,r.url) END display_name,r.url acquired_url,r.axe_violations,r.lighthouse_score,r.wave_aim_score,r.evaluated_at,e.title,d.storage_key,o.relative_path,r.source_snapshot_path,r.response_source_path FROM experiment_results r JOIN experiments e ON e.id=r.experiment_id LEFT JOIN dataset_observations o ON o.id=r.dataset_observation_id LEFT JOIN datasets d ON d.id=o.dataset_id WHERE r.status='completed' ORDER BY r.evaluated_at DESC,r.id DESC""")
    sources=cursor.fetchall()
    for row in sources: row["snapshot_available"]=bool(source_snapshot(row))
    cursor.close(); conn.close()
    return render_template("remediation_runs.html",sources=sources,llms=options,model_choices=model_choices(settings),expert_models={c['model']:c['name'] for c in model_choices(settings)},rag=rag_status(),common_conditions=common_conditions(settings))


@remediation_bp.post("/<int:run_id>/compare")
def compare_with_original(run_id):
    from routes.comparisons import insert_members, insert_remediation_members
    conn=get_connection(); cursor=conn.cursor(dictionary=True)
    cursor.execute("""SELECT rr.id,rr.source_result_id,COALESCE(er.display_name,o.display_name,o.observation_key,er.url) source_name
                      FROM remediation_runs rr JOIN experiment_results er ON er.id=rr.source_result_id
                      LEFT JOIN dataset_observations o ON o.id=er.dataset_observation_id
                      WHERE rr.id=%s AND rr.status IN ('accepted','completed_with_warnings')""",(run_id,)); run=cursor.fetchone()
    if not run:
        cursor.close(); conn.close(); flash(_("Only an accepted remediation can be compared with its original."),"warning"); return redirect(url_for("remediation.run_detail",run_id=run_id))
    try:
        timestamp=now_local(); title=f"{run['source_name']} · original vs remediated"[:160]
        cursor.execute("INSERT INTO comparison_studies (title,dimension_label,created_at,updated_at) VALUES (%s,'Version',%s,%s)",(title,timestamp,timestamp)); comparison_id=cursor.lastrowid
        insert_members(cursor,comparison_id,[run["source_result_id"]],"Original")
        insert_remediation_members(cursor,comparison_id,[run_id],"Remediated")
        cursor.execute("UPDATE comparison_members SET is_baseline=TRUE,pair_key=%s WHERE comparison_id=%s AND source_result_id=%s",(f"remediation-{run_id}",comparison_id,run["source_result_id"]))
        cursor.execute("UPDATE comparison_members SET pair_key=%s WHERE comparison_id=%s AND source_remediation_run_id=%s",(f"remediation-{run_id}",comparison_id,run_id))
        conn.commit()
    except Exception:
        conn.rollback(); cursor.close(); conn.close(); flash(_("The comparison could not be created."),"danger"); return redirect(url_for("remediation.run_detail",run_id=run_id))
    cursor.close(); conn.close()
    return redirect(url_for("comparisons.comparisons",comparison_id=comparison_id))


@remediation_bp.get("/<int:run_id>")
def run_detail(run_id):
    conn=get_connection(); cursor=conn.cursor(dictionary=True)
    cursor.execute("""SELECT rr.*,COALESCE(r.display_name,r.page_title,r.url) source_name,r.url source_url,r.axe_violations original_axe,r.lighthouse_score original_lighthouse,r.wave_aim_score original_aim,t.name template_name FROM remediation_runs rr JOIN experiment_results r ON r.id=rr.source_result_id LEFT JOIN remediation_templates t ON t.id=rr.template_id WHERE rr.id=%s""",(run_id,)); run=cursor.fetchone()
    if not run: cursor.close(); conn.close(); return redirect(url_for("remediation.runs"))
    cursor.execute("SELECT * FROM remediation_iterations WHERE run_id=%s ORDER BY iteration_number",(run_id,)); iterations=cursor.fetchall()
    cursor.execute("SELECT * FROM remediation_events WHERE run_id=%s ORDER BY id",(run_id,)); events=cursor.fetchall()
    model_roles={}; category_counts={"Syntactic":0,"Semantic":0,"Layout":0}; taxonomy=None
    for item in iterations:
        for field,target in (("dom_changes_json","dom_changes"),("specialist_reviews_json","specialist_reviews"),("agent_usage_json","agent_usage"),("strategy_json","strategy")):
            fallback="{}" if target in {"dom_changes","strategy"} else "[]"
            try: item[target]=json.loads(item.get(field) or fallback)
            except (ValueError,TypeError): item[target]={} if target=="dom_changes" else []
        if run.get('execution_mode')=='single_shot' and item.get('strategy'):
            # Present old evidence with current process terminology; do not
            # rewrite stored prompts, model responses or scientific provenance.
            item['strategy'].setdefault('approach',{})['name']='Zero-shot — single call'
            item['strategy']['repair_engine']='Zero-shot prompting; one generation call; no planner, checker feedback, RAG, screenshot or repair postprocessor'
        recorded_roles=[(entry.get('role') or 'Agent',entry.get('model')) for entry in item['agent_usage'] if isinstance(entry,dict)]
        if not recorded_roles:
            recorded_roles=[('Generator',item.get('generator_model'))]
            if run.get('review_policy') != 'automated':
                recorded_roles.append(('Coordinator',item.get('reviewer_model')))
        for role,model in recorded_roles:
            if model and not model.startswith("system/"): model_roles.setdefault(model,set()).add(role)
        for review in item["specialist_reviews"]:
            if review.get("model"): model_roles.setdefault(review["model"],set()).add(review.get("role") or "Specialist")
            if review.get("status") in {"advisory","blocker"} and review.get("category") in category_counts:
                category_counts[review["category"]]+=max(1,len(review.get("findings") or []))
        if item.get("strategy",{}).get("taxonomy"):
            taxonomy=item["strategy"]["taxonomy"]
    participants=[{"model":model,"roles":", ".join(sorted(roles))} for model,roles in model_roles.items()]
    accepted_item=next((item for item in reversed(iterations) if item.get("decision")=="accept"),None)
    measurable=[item for item in iterations if item.get("axe_violations") is not None and item.get("lighthouse_score") is not None]
    retained_item=next((item for item in iterations if item['id']==run.get('accepted_iteration_id')),None)
    best=retained_item or accepted_item or (min(measurable,key=lambda item:max(float(item["axe_violations"])-float(run["max_axe"]),0)+max(float(run["min_lighthouse"])-float(item["lighthouse_score"]),0)) if measurable else None)
    run["improvement"]=improvement_metrics(run.get("original_axe"),best.get("axe_violations") if best else None,run.get("original_lighthouse"),best.get("lighthouse_score") if best else None)
    run['presentation_priority']=presentation_priority(run.get('accessibility_priority'),best.get('strategy',{}) if best else None)
    initial_strategy=iterations[0].get('strategy',{}) if iterations else {}
    run['presentation_name']=presentation_name(run.get('accessibility_priority'),initial_strategy)
    cursor.close(); conn.close()
    report_candidate_available=bool(best and best.get('output_path') and Path(best['output_path']).is_file())
    return render_template("remediation_detail.html",run=run,iterations=iterations,participants=participants,events=events,category_counts=category_counts,taxonomy=taxonomy,best_candidate=best,report_candidate_available=report_candidate_available)


@remediation_bp.get("/<int:run_id>/iterations/<int:iteration_id>/candidate")
def candidate_file(run_id, iteration_id):
    conn=get_connection(); cursor=conn.cursor(dictionary=True)
    cursor.execute("SELECT output_path FROM remediation_iterations WHERE id=%s AND run_id=%s",(iteration_id,run_id)); item=cursor.fetchone(); cursor.close(); conn.close()
    path=Path(item["output_path"]).resolve() if item and item.get("output_path") else None
    allowed=(DATASET_ROOT/"remediations").resolve()
    if not path or allowed not in path.parents or not path.is_file(): return Response(status=404)
    return send_file(path,mimetype="text/html",conditional=True)


@remediation_bp.get("/<int:run_id>/iterations/<int:iteration_id>/screenshot")
def candidate_screenshot(run_id, iteration_id):
    conn=get_connection(); cursor=conn.cursor(dictionary=True)
    cursor.execute("SELECT screenshot_path FROM remediation_iterations WHERE id=%s AND run_id=%s",(iteration_id,run_id)); item=cursor.fetchone(); cursor.close(); conn.close()
    path=Path(item["screenshot_path"]).resolve() if item and item.get("screenshot_path") else None
    allowed=Path("/results/raw").resolve()
    if not path or allowed not in path.parents or not path.is_file(): return Response(status=404)
    return send_file(path,mimetype="image/jpeg",conditional=True)


@remediation_bp.get("/<int:run_id>/original/screenshot")
def original_screenshot(run_id):
    conn=get_connection(); cursor=conn.cursor(dictionary=True)
    cursor.execute("SELECT r.screenshot_path FROM remediation_runs rr JOIN experiment_results r ON r.id=rr.source_result_id WHERE rr.id=%s",(run_id,)); item=cursor.fetchone(); cursor.close(); conn.close()
    path=Path(item["screenshot_path"]).resolve() if item and item.get("screenshot_path") else None
    allowed=Path("/results/raw").resolve()
    if not path or allowed not in path.parents or not path.is_file(): return Response(status=404)
    return send_file(path,mimetype="image/jpeg",conditional=True)
