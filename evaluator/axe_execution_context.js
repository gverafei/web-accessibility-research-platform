const { randomUUID, createHash } = require('node:crypto');
const { source } = require('axe-core');

// Audit logging must not enter page-owned console hooks, which can throw or
// recurse when a captured analytics widget initializes again during replay.
async function prepareAxeExecutionContext(context) {
  const key = `__a11y_console_${randomUUID().replaceAll('-', '')}`;
  await context.addInitScript(({ key }) => {
    const native = {};
    for (const name of Object.getOwnPropertyNames(console)) {
      if (typeof console[name] === 'function') native[name] = console[name].bind(console);
    }
    Object.defineProperty(window, key, { value: Object.freeze(native), enumerable: false });
  }, { key });
  return {
    source: `(function(console){${source}\n})(window[${JSON.stringify(key)}] || window.console);`,
    evidence: { version: 'native-console-v1', core_source_sha256: createHash('sha256').update(source).digest('hex') }
  };
}

module.exports = { prepareAxeExecutionContext };
