const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

test('each intervention repaints its card and range accent without changing the model', () => {
  const elements = new Map();
  const accents = new Map();
  const context = vm.createContext({document: {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, {});
      return elements.get(id);
    },
    querySelector(selector) {
      return {style: {setProperty(key, value) {accents.set(`${selector}:${key}`, value);}}};
    }
  }});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../controls.js'), 'utf8'), context);
  const colors = ['#2f9e66', '#2686c9', '#6558c8', '#9b4fc2', '#c3486b'];
  context.fixture = {
    models: [{id: 'openai/gpt-6-luna', name: 'Luna · Light reasoning', tier:'medium', color: '#2f9e66'}],
    preservation: colors.map((color, i) => ({color, name: `Level ${i}`, instruction: 'Repair',
      recipe: {lighthouse: 94, axe: 3, iterations: 3, temperature: 0.05, rag_top_k: 4, cost: 0.15, seconds: 240}})),
    ui_copy: Object.fromEntries(['en', 'es'].map(locale => [locale, {
      preservation: colors.map((_, i) => ({name: `${locale} name ${i}`, subtitle: `${locale} subtitle ${i}`, description: `${locale} description ${i}`})),
      labels: {temperature: 'Temperature', iterations: 'iterations', act: 'ACT examples after failure', native: 'Native / scoped components'}
    }]))
  };
  vm.runInContext('extensionControls.catalog = fixture', context);
  for (const locale of ['en', 'es']) {
    colors.forEach((color, i) => {
      vm.runInContext(`extensionControls.paint('${locale}', 0, ${i})`, context);
      assert.equal(accents.get('.slider-card.preservation:--accent'), color);
      assert.equal(accents.get('.slider-card.model:--accent'), '#2f9e66');
      assert.equal(elements.get('modelName').textContent, 'Medium');
      assert.equal(elements.get('modelIdentity').textContent, 'Luna · Light reasoning');
      assert.equal(elements.get('preservationName').textContent, `${locale} name ${i}`);
      assert.equal(elements.get('preservationSubtitle').textContent, `${locale} subtitle ${i}`);
      assert.equal(elements.get('preservationDetail').textContent, `${locale} description ${i}`);
      const framework = i >= 3 ? 'Bootstrap 5.3.8' : 'Native / scoped components';
      assert.equal(elements.get('recipe').textContent, `${locale} name ${i} · ${framework} · Temperature 0.05 · 3 iterations · Lighthouse ≥94 · Axe ≤3.`);
      assert.doesNotMatch(elements.get('recipe').textContent, /\$|240|seconds/);
      elements.get('useRag').checked = true;
      vm.runInContext(`extensionControls.paint('${locale}', 0, ${i})`, context);
      assert.match(elements.get('recipe').textContent, /4–12 ACT examples after failure\.$/);
      elements.get('useRag').checked = false;
    });
  }
});
