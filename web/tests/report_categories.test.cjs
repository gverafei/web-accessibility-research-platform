const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const template = fs.readFileSync(path.join(__dirname, '../app/templates/report.html'), 'utf8');
const comparatorBody = template.split('rows.sort((a,b)=>{')[1].split('});rows.forEach')[0];
const comparator = (column, direction) => new Function('column', 'direction', 'document',
  `return (a,b)=>{${comparatorBody}}`)(column, direction, {documentElement: {lang: 'en'}});
const row = value => ({dataset: {site_category: value, axe_total: value}});

test('category sorting uses text in both directions, including unclassified', () => {
  const values = ['Technology', 'Business', 'Unclassified', 'Gaming'];
  assert.deepEqual(values.map(row).sort(comparator('site_category', 'asc'))
    .map(item => item.dataset.site_category), ['Business', 'Gaming', 'Technology', 'Unclassified']);
  assert.deepEqual(values.map(row).sort(comparator('site_category', 'desc'))
    .map(item => item.dataset.site_category), ['Unclassified', 'Technology', 'Gaming', 'Business']);
});

test('numeric measurements retain numeric sorting and put missing values last', () => {
  assert.deepEqual(['14', '', '2', '100'].map(row).sort(comparator('axe_total', 'asc'))
    .map(item => item.dataset.axe_total), ['2', '14', '100', '']);
});
