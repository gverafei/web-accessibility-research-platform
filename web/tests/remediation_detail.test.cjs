const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname, '../app/static/js/remediation_detail.js'), 'utf8');

function fixture(status = 'running') {
  const state = {timers: [], fetches: [], hidden: false, selection: '', failed: false, scroll: null};
  const detail = (count, open) => ({dataset:{reportPanel:'activity-log'}, open,
    closest:()=>null, querySelector:()=>({textContent:`Activity ${count} events`, focus(){}})});
  const node = (status, count) => ({dataset:{runStatus:status}, detail:detail(count,false),
    querySelectorAll(selector){return selector==='details[open]' ? (this.detail.open?[this.detail]:[]) : selector==='details'?[this.detail]:[];},
    querySelector:()=>null, contains:()=>false, replaceWith(next){state.root=next;}});
  state.root=node(status,1); state.root.detail.open=true;
  const document={getElementById:()=>state.root, get hidden(){return state.hidden;},
    getSelection:()=>({toString:()=>state.selection}), activeElement:null};
  const window={location:{href:'http://localhost/remediation/7'},scrollY:300,
    scrollTo:value=>{state.scroll=value.top;},addEventListener(){}};
  class DOMParser {parseFromString(){return {getElementById:()=>node('accepted',2)};}}
  const fetch=async (url, options)=>{
    state.fetches.push({url,options}); if(state.failed) throw Error('offline');
    return {ok:true,text:async()=>'actual refreshed report'};
  };
  vm.runInNewContext(code,{document,window,fetch,URL,DOMParser,AbortController,
    setTimeout:(fn,ms)=>{if(ms===4000)state.timers.push(fn);return 1;},clearTimeout(){}});
  return state;
}
test('live report preserves an open activity panel as event counts change, and stops on completion', async()=>{
  const s=fixture(); await s.timers.shift()();
  assert.equal(s.root.dataset.runStatus,'accepted'); assert.equal(s.root.detail.open,true);
  assert.equal(s.scroll,300); assert.equal(s.timers.length,0);
  assert.equal(s.fetches[0].url.searchParams.get('live'),'1');
  assert.equal(s.fetches[0].options.cache,'no-store');
});
test('failed requests keep the old report and retry',async()=>{
  const s=fixture(); s.failed=true; const original=s.root;
  await s.timers.shift()(); assert.equal(s.root,original); assert.equal(s.timers.length,1);
});
test('hidden and selected text defer read-only requests',async()=>{
  const s=fixture(); s.hidden=true; await s.timers.shift()();
  s.hidden=false; s.selection='copied prompt'; await s.timers.shift()();
  assert.equal(s.fetches.length,0); assert.equal(s.timers.length,1);
});
test('terminal reports do not poll',()=>assert.equal(fixture('accepted').timers.length,0));
