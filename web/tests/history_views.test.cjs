const test = require('node:test');
const assert = require('node:assert/strict');
const {init} = require('../app/static/js/history_views.js');

function fixture(saved, blocked=false) {
  const views = [{dataset:{}}, {dataset:{}}];
  const buttons = views.map(() => ['table','cards'].map(mode => ({dataset:{historyMode:mode},
    setAttribute(name,value){this[name]=value;},closest(){return this;}})));
  const controls = views.map((_,i) => ({dataset:{historyViewControls:String(i)},
    querySelectorAll:()=>buttons[i],contains:b=>buttons[i].includes(b),
    addEventListener(_,fn){this.click=fn;}}));
  const storage = {getItem(){if(blocked)throw Error();return saved;},
    setItem(key,value){if(blocked)throw Error();this.saved=[key,value];}};
  init({document:{querySelectorAll:()=>controls,getElementById:id=>views[id]},localStorage:storage});
  return {views,buttons,controls,storage};
}
test('table default and card preference are shared between histories',()=>{
  const s=fixture(); assert.deepEqual(s.views.map(v=>v.dataset.historyView),['table','table']);
  s.controls[0].click({target:s.buttons[0][1]});
  assert.deepEqual(s.views.map(v=>v.dataset.historyView),['cards','cards']);
  assert.equal(s.buttons[1][1]['aria-pressed'],'true');
  assert.equal(s.buttons[1][0]['aria-pressed'],'false');
  assert.deepEqual(s.storage.saved,['history-list-view','cards']);
  s.controls[1].click({target:s.buttons[1][0]});
  assert.equal(s.views[0].dataset.historyView,'table');
});
test('restores cards, ignores unknown values and works without browser storage',()=>{
  assert.equal(fixture('cards').views[0].dataset.historyView,'cards');
  assert.equal(fixture('garbage').views[0].dataset.historyView,'table');
  const s=fixture(null,true); s.controls[0].click({target:s.buttons[0][1]});
  assert.equal(s.views[0].dataset.historyView,'cards');
});
test('only a view control can change the mode',()=>{
  const s=fixture(); s.controls[0].click({target:{closest:()=>null}});
  s.controls[0].click({target:{closest:()=>({dataset:{historyMode:'cards'}})}});
  assert.equal(s.views[0].dataset.historyView,'table');
});
