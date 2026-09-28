const express = require("express");
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const { loadPolicy } = require("./run_axe");
const { runAxeIsolated: runAxe } = require("./run_axe_isolated");
const { runLighthouse } = require("./run_lighthouse");
const { runWave } = require("./run_wave");
const { safeFileName } = require("./file_names");

const app = express();
app.use(express.json({ limit: "20mb" }));

const RESULTS_DIR = "/results/raw";

function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

function getCommandOutput(command) {
  try {
    return execSync(command, { encoding: "utf-8" }).trim();
  } catch {
    return "unknown";
  }
}

function getPackageVersion(packageName) {
  try {
    const output = execSync(`npm list ${packageName} --depth=0 --json`, {
      encoding: "utf-8"
    });
    const parsed = JSON.parse(output);
    return parsed.dependencies?.[packageName]?.version || "unknown";
  } catch {
    return "unknown";
  }
}

function getEnvironmentMetadata(executionSeconds, includeWave, axeStandard, axeIncludeBestPractices, runtimeConfig = {}) {
  const policy = loadPolicy(runtimeConfig);
  return {
    docker_web_image: process.env.DOCKER_WEB_IMAGE || "local-build",
    docker_evaluator_image: process.env.DOCKER_EVALUATOR_IMAGE || "local-build",
    python_version: null,
    node_version: getCommandOutput("node --version"),
    chromium_version: getCommandOutput("chromium --version"),
    axe_version: getPackageVersion("@axe-core/playwright"),
    axe_standard: axeStandard,
    axe_include_best_practices: axeIncludeBestPractices,
    axe_counting_mode: "issue_instances",
    app_timezone: runtimeConfig.app_timezone || process.env.APP_TIMEZONE || "UTC",
    lighthouse_version: getPackageVersion("lighthouse"),
    openai_model: null,
    llm_provider: null,
    llm_model: null,
    wave_api_version: includeWave ? "3.1" : null,
    wave_report_type: includeWave
      ? Number.parseInt(runtimeConfig.wave_report_type ?? process.env.WAVE_REPORT_TYPE ?? "2", 10)
      : null,
    wave_eval_delay_ms: includeWave
      ? Number.parseInt(runtimeConfig.wave_eval_delay_ms ?? process.env.WAVE_EVAL_DELAY_MS ?? "2000", 10)
      : null,
    page_load_timeout_ms: policy.page_load_timeout_ms,
    network_idle_timeout_ms: policy.network_idle_timeout_ms,
    page_settle_delay_ms: policy.page_settle_delay_ms,
    dom_stability_window_ms: policy.dom_stability_window_ms,
    dom_stability_timeout_ms: policy.dom_stability_timeout_ms,
    lazy_load_scroll: policy.lazy_load_scroll,
    scroll_step_px: policy.scroll_step_px,
    scroll_delay_ms: policy.scroll_delay_ms,
    max_scroll_steps: policy.max_scroll_steps,
    evaluator_concurrency: "axe+lighthouse+wave per URL; Axe/Lighthouse isolated process supervision v1",
    execution_seconds: executionSeconds
  };
}

app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    service: "accessibility-evaluator",
    axe_version: getPackageVersion("@axe-core/playwright")
  });
});

app.post("/evaluate", async (req, res) => {
  const experimentStart = Date.now();
  const {
    experiment_id,
    urls,
    include_wave = false,
    axe_standard = "wcag22aa",
    axe_include_best_practices = false,
    runtime_config = {},
    quality_policy = {}
  } = req.body;

  if (!experiment_id || !Array.isArray(urls) || urls.length === 0) {
    return res.status(400).json({
      error: "experiment_id y urls son requeridos"
    });
  }
  const { validateQualityPolicy, evidenceRejection } = require('./acquisition_quality');
  try { validateQualityPolicy(quality_policy); }
  catch (error) { return res.status(400).json({error: error.message}); }

  ensureDir(RESULTS_DIR);

  const experimentDir = path.join(RESULTS_DIR, `experiment_${experiment_id}`);
  ensureDir(experimentDir);

  const results = [];

  for (const url of urls) {
    const itemStart = Date.now();
    const fileBase = safeFileName(url);
    const screenshotPath = path.join(experimentDir, `${fileBase}_page.jpg`);

    try {
      const skippedWave = {
        status: "skipped",
        error: null,
        report_type: null,
        credits_used: 0,
        cost_usd: 0,
        summary: {
          errors: 0, contrast_errors: 0, alerts: 0, features: 0,
          structure: 0, aria: 0, aim_score: null, total_elements: 0
        },
        raw: null
      };
      const [axeOutcome, lighthouseOutcome, waveOutcome] = await Promise.allSettled([
        runAxe(url, screenshotPath, {
          standard: axe_standard,
          includeBestPractices: true,
          runtimeConfig: runtime_config,
          qualityPolicy: quality_policy
        }),
        runLighthouse(url),
        include_wave === true ? runWave(url, runtime_config) : Promise.resolve(skippedWave)
      ]);

      if (axeOutcome.status === "rejected" || lighthouseOutcome.status === "rejected") {
        const failures = [];
        if (axeOutcome.status === "rejected") failures.push(`Axe: ${axeOutcome.reason.message}`);
        if (lighthouseOutcome.status === "rejected") failures.push(`Lighthouse: ${lighthouseOutcome.reason.message}`);
        throw new Error(failures.join(" | "));
      }

      const axeResult = axeOutcome.value;
      const lighthouseResult = lighthouseOutcome.value;
      const incomplete = evidenceRejection(axeResult, quality_policy);
      if (incomplete) throw new Error(incomplete);

      const axePath = path.join(experimentDir, `${fileBase}_axe.json`);
      const lighthousePath = path.join(experimentDir, `${fileBase}_lighthouse.json`);
      const sourceSnapshotPath = path.join(experimentDir, `${fileBase}_source.html`);
      const responseSourcePath = axeResult.response_html
        ? path.join(experimentDir, `${fileBase}_response.html`)
        : null;

      fs.writeFileSync(axePath, JSON.stringify(axeResult.raw, null, 2), "utf-8");
      fs.writeFileSync(lighthousePath, JSON.stringify(lighthouseResult.raw, null, 2), "utf-8");
      fs.writeFileSync(sourceSnapshotPath, axeResult.html, "utf-8");
      if (responseSourcePath) fs.writeFileSync(responseSourcePath, axeResult.response_html, "utf-8");

      let waveResult = waveOutcome.status === "fulfilled"
        ? waveOutcome.value
        : { ...skippedWave, status: "failed", error: waveOutcome.reason.message };
      let wavePath = null;

      if (waveResult.raw) {
        wavePath = path.join(experimentDir, `${fileBase}_wave.json`);
        fs.writeFileSync(
          wavePath,
          JSON.stringify(waveResult.raw, null, 2),
          "utf-8"
        );
      }

      const executionSeconds = (Date.now() - itemStart) / 1000;

      results.push({
        url,
        status: "completed",
        execution_seconds: executionSeconds,
        html_metrics: axeResult.html_metrics,
        load_metadata: axeResult.load_metadata,
        screenshot_path: axeResult.screenshot_path,
        screenshot_mode: axeResult.screenshot_mode,
        acquisition: axeResult.acquisition,
        source_snapshot_path: sourceSnapshotPath,
        response_source_path: responseSourcePath,
        axe: {
          violations: axeResult.summary.violations,
          critical: axeResult.summary.critical,
          serious: axeResult.summary.serious,
          moderate: axeResult.summary.moderate,
          minor: axeResult.summary.minor,
          failed_rules: axeResult.summary.failed_rules,
          critical_rules: axeResult.summary.critical_rules,
          serious_rules: axeResult.summary.serious_rules,
          moderate_rules: axeResult.summary.moderate_rules,
          minor_rules: axeResult.summary.minor_rules,
          needs_review: axeResult.summary.needs_review,
          needs_review_rules: axeResult.summary.needs_review_rules,
          best_practice_issues: axeResult.summary.best_practice_issues,
          best_practice_rules: axeResult.summary.best_practice_rules,
          wcag_violations: axeResult.summary.wcag_violations,
          wcag_critical: axeResult.summary.wcag_critical,
          wcag_serious: axeResult.summary.wcag_serious,
          wcag_moderate: axeResult.summary.wcag_moderate,
          wcag_minor: axeResult.summary.wcag_minor,
          wcag_failed_rules: axeResult.summary.wcag_failed_rules,
          wcag_needs_review: axeResult.summary.wcag_needs_review,
          raw_path: axePath
        },
        lighthouse: {
          accessibility_score: lighthouseResult.summary.accessibility_score,
          raw_path: lighthousePath
        },
        wave: {
          status: waveResult.status,
          report_type: waveResult.report_type,
          errors: waveResult.summary.errors,
          contrast_errors: waveResult.summary.contrast_errors,
          alerts: waveResult.summary.alerts,
          features: waveResult.summary.features,
          structure: waveResult.summary.structure,
          aria: waveResult.summary.aria,
          aim_score: waveResult.summary.aim_score,
          total_elements: waveResult.summary.total_elements,
          credits_used: waveResult.credits_used || 0,
          cost_usd: waveResult.cost_usd || 0,
          raw_path: wavePath,
          error: waveResult.error
        }
      });

    } catch (error) {
      results.push({
        url,
        status: "failed",
        error: error.message,
        execution_seconds: (Date.now() - itemStart) / 1000
      });
    }
  }

  const totalExecutionSeconds = (Date.now() - experimentStart) / 1000;

  res.json({
    experiment_id,
    status: "completed",
    environment: getEnvironmentMetadata(
      totalExecutionSeconds,
      include_wave === true,
      axe_standard,
      true,
      runtime_config
    ),
    results
  });
});

app.listen(3000, "0.0.0.0", () => {
  console.log("Evaluator service running on port 3000");
});
