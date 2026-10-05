const test = require('node:test');
const assert = require('node:assert/strict');
const {filterRows, selectionState, orderedRows, availableSpace} = require('../app/static/js/combine_lists.js');

function box(search, checked=false, disabled=false) {
  const row = {hidden: false, dataset: {search}};
  return {checked, disabled, row, closest: () => row};
}
test('filters rows without discarding selected or staged pages', () => {
  const a=box('https://php.net/', true), b=box('https://example.org/');
  filterRows([a.row,b.row], ' PHP ');
  assert.equal(a.row.hidden,false);assert.equal(b.row.hidden,true);
  assert.equal(a.checked,true);
  filterRows([a.row,b.row], '');assert.equal(b.row.hidden,false);
});
test('toolbar shows all selected, while select-all describes eligible visible rows', () => {
  const a=box('a',true),b=box('b',true),c=box('c',true,true);
  b.row.hidden=true;
  const all={},count={};
  assert.equal(selectionState(all,[a,b,c],count),2);
  assert.equal(count.textContent,2);assert.equal(all.checked,true);
  assert.equal(all.indeterminate,false);assert.equal(all.disabled,false);
});
test('partial and empty views retain correct checkbox states', () => {
  const a=box('a',true),b=box('b'),all={},count={};
  selectionState(all,[a,b],count);
  assert.equal(all.indeterminate,true);assert.equal(all.checked,false);
  a.row.hidden=b.row.hidden=true;
  selectionState(all,[a,b],count);
  assert.equal(all.disabled,true);assert.equal(all.checked,false);
  assert.equal(all.indeterminate,false);assert.equal(count.textContent,1);
});
test('URL sorting alternates direction without changing row state or the input list', () => {
  const rows=['https://z.org/','https://a.org/','https://b.org/'].map(url=>({dataset:{url},hidden:false,checked:true}));
  assert.deepEqual(orderedRows(rows).map(r=>r.dataset.url),['https://a.org/','https://b.org/','https://z.org/']);
  assert.deepEqual(orderedRows(rows,true).map(r=>r.dataset.url),['https://z.org/','https://b.org/','https://a.org/']);
  assert.equal(rows[0].dataset.url,'https://z.org/');assert.equal(rows[0].checked,true);
});
test('available height accounts for the actual heading and never invents a minimum panel height', () => {
  assert.equal(availableSpace(900,210),666);
  assert.equal(availableSpace(700,250),426);
  assert.equal(availableSpace(200,250),0);
});
