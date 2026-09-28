const path = require("node:path");
const { runIsolatedNode } = require("./isolated_process");
const { loadPolicy } = require("./run_axe");

async function runAxeIsolated(url, screenshotPath, options = {}) {
  const policy = loadPolicy(options.runtimeConfig || {});
  let output;
  try {
    output = await runIsolatedNode([
      path.join(__dirname, "run_axe_direct.js"), JSON.stringify({ url, screenshotPath, options })
    ], { timeoutMs: Math.max(1, policy.axe_hard_timeout_ms) + 10000 });
  } catch (error) {
    throw new Error(`Isolated Axe failure: ${error.message}`, { cause: error });
  }
  try { return JSON.parse(output); }
  catch (error) { throw new Error(`Isolated Axe returned invalid JSON: ${error.message}`, { cause: error }); }
}

module.exports = { runAxeIsolated };
