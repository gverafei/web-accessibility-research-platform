const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Exercise the actual shared report plugin, not a duplicate configuration.
const template = fs.readFileSync(path.join(__dirname, '../app/templates/report.html'), 'utf8');
const source = template.split('\n').find(line => line.includes('id:"warpBarVisuals"'));
assert.ok(source, 'report registers its shared bar plugin');
let plugin;
const Chart = {register(value) {plugin = value;}, defaults: {datasets: {bar: {}}}};
vm.runInNewContext(source, {Chart});

test('horizontal bars identify the hovered URL by y and retain every stacked impact', () => {
    const chart = {config: {type: 'bar'}, options: {indexAxis: 'y'},
        data: {datasets: ['critical', 'serious', 'moderate', 'minor']}};
    plugin.beforeInit(chart);
    assert.equal(chart.options.interaction.axis, 'y');
    assert.equal(chart.options.interaction.mode, 'index');
    assert.equal(chart.options.interaction.intersect, false);
    assert.deepEqual(chart.data.datasets, ['critical', 'serious', 'moderate', 'minor']);
});

test('vertical bar charts select their category by x, including the implicit default', () => {
    for (const options of [{}, {indexAxis: 'x'}]) {
        const chart = {config: {type: 'bar'}, options};
        plugin.beforeInit(chart);
        assert.equal(chart.options.interaction.axis, 'x');
        assert.equal(chart.options.interaction.mode, 'index');
    }
});

test('nonbar chart interaction is left unchanged', () => {
    for (const type of ['scatter', 'line', 'boxplot']) {
        const interaction = {mode: 'nearest', intersect: true};
        const chart = {config: {type}, options: {interaction}};
        plugin.beforeInit(chart);
        assert.strictEqual(chart.options.interaction, interaction);
    }
});
