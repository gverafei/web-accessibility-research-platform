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
    models: [{id: 'openai/gpt-6-luna', name: 'Luna', color: '#2f9e66'}],
    preservation: colors.map((color, i) => ({color, name: `Level ${i}`, instruction: 'Repair',
      recipe: {lighthouse: 94, axe: 3, iterations: 3, cost: 0.15, seconds: 240}}))
  };
  vm.runInContext('extensionControls.catalog = fixture', context);
  for (const locale of ['en', 'es']) {
    colors.forEach((color, i) => {
      vm.runInContext(`extensionControls.paint('${locale}', 0, ${i})`, context);
      assert.equal(accents.get('.slider-card.preservation:--accent'), color);
      assert.equal(accents.get('.slider-card.model:--accent'), '#2f9e66');
    });
  }
});
