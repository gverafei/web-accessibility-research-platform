const assert = require("node:assert/strict");
const test = require("node:test");

const { runWave } = require("../run_wave");

test("WAVE returns skipped when the API key is missing", async () => {
  const previousKey = process.env.WAVE_API_KEY;
  delete process.env.WAVE_API_KEY;

  try {
    const result = await runWave("https://example.com");
    assert.equal(result.status, "skipped");
    assert.equal(result.summary.errors, 0);
  } finally {
    if (previousKey === undefined) {
      delete process.env.WAVE_API_KEY;
    } else {
      process.env.WAVE_API_KEY = previousKey;
    }
  }
});

test("WAVE normalizes a successful API response", async () => {
  const previousKey = process.env.WAVE_API_KEY;
  const previousFetch = global.fetch;
  const previousDelay = process.env.WAVE_EVAL_DELAY_MS;
  process.env.WAVE_API_KEY = "test-key";
  process.env.WAVE_EVAL_DELAY_MS = "2500";

  global.fetch = async (requestUrl) => {
    assert.match(requestUrl, /reporttype=2/);
    assert.match(requestUrl, /evaldelay=2500/);
    assert.doesNotMatch(requestUrl, /test-key.*test-key/);
    return {
      ok: true,
      json: async () => ({
        status: { success: true, httpstatuscode: 200 },
        statistics: { AIMscore: 8.5, totalelements: 120 },
        categories: {
          error: { count: 2 },
          contrast: { count: 3 },
          alert: { count: 4 },
          feature: { count: 5 },
          structure: { count: 6 },
          aria: { count: 7 }
        }
      })
    };
  };

  try {
    const result = await runWave("https://example.com");
    assert.equal(result.status, "completed");
    assert.deepEqual(result.summary, {
      errors: 2,
      contrast_errors: 3,
      alerts: 4,
      features: 5,
      structure: 6,
      aria: 7,
      aim_score: 8.5,
      total_elements: 120
    });
  } finally {
    global.fetch = previousFetch;
    if (previousDelay === undefined) delete process.env.WAVE_EVAL_DELAY_MS;
    else process.env.WAVE_EVAL_DELAY_MS = previousDelay;
    if (previousKey === undefined) {
      delete process.env.WAVE_API_KEY;
    } else {
      process.env.WAVE_API_KEY = previousKey;
    }
  }
});
