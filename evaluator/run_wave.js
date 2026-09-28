const WAVE_API_URL = "https://wave.webaim.org/api/request";

function emptySummary() {
  return {
    errors: 0,
    contrast_errors: 0,
    alerts: 0,
    features: 0,
    structure: 0,
    aria: 0,
    aim_score: null,
    total_elements: 0
  };
}

function categoryCount(payload, category) {
  return Number(payload.categories?.[category]?.count || 0);
}

function creditsForReportType(reportType) {
  return reportType === 1 ? 1 : reportType === 2 ? 2 : 3;
}

async function runWave(url, config = {}) {
  const apiKey = String(config.wave_api_key ?? process.env.WAVE_API_KEY ?? "").trim();
  const configuredReportType = Number.parseInt(
    config.wave_report_type ?? process.env.WAVE_REPORT_TYPE ?? "2",
    10
  );
  const reportType = [1, 2, 3, 4].includes(configuredReportType)
    ? configuredReportType
    : 2;
  const configuredEvalDelay = Number.parseInt(
    config.wave_eval_delay_ms ?? process.env.WAVE_EVAL_DELAY_MS ?? "2000",
    10
  );
  const evalDelay = Number.isFinite(configuredEvalDelay) && configuredEvalDelay >= 0
    ? configuredEvalDelay
    : 2000;

  if (!apiKey || apiKey.toLowerCase().startsWith("coloca_aqui")) {
    return {
      status: "skipped",
      error: "WAVE_API_KEY is not configured.",
      report_type: reportType,
      summary: emptySummary(),
      raw: null
    };
  }

  const parameters = new URLSearchParams({
    key: apiKey,
    url,
    format: "json",
    reporttype: String(reportType),
    evaldelay: String(evalDelay)
  });

  const response = await fetch(`${WAVE_API_URL}?${parameters.toString()}`, {
    signal: AbortSignal.timeout(120000)
  });

  if (!response.ok) {
    throw new Error(`WAVE API returned HTTP ${response.status}.`);
  }

  const payload = await response.json();

  if (payload.status?.success !== true) {
    return {
      status: "failed",
      error: payload.status?.error || "WAVE API reported an unsuccessful evaluation.",
      report_type: reportType,
      summary: emptySummary(),
      raw: payload
    };
  }

  return {
    status: "completed",
    error: null,
    report_type: reportType,
    credits_used: creditsForReportType(reportType),
    cost_usd: creditsForReportType(reportType) * Number.parseFloat(config.wave_cost_per_credit_usd ?? process.env.WAVE_COST_PER_CREDIT_USD ?? "0.04"),
    summary: {
      errors: categoryCount(payload, "error"),
      contrast_errors: categoryCount(payload, "contrast"),
      alerts: categoryCount(payload, "alert"),
      features: categoryCount(payload, "feature"),
      structure: categoryCount(payload, "structure"),
      aria: categoryCount(payload, "aria"),
      aim_score: payload.statistics?.AIMscore ?? null,
      total_elements: Number(payload.statistics?.totalelements || 0)
    },
    raw: payload
  };
}

module.exports = { runWave };
