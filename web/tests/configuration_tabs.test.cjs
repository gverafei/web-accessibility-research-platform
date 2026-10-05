const {test}=require('node:test');
const assert=require('node:assert/strict');
const {init}=require('../app/static/js/configuration_tabs.js');
function fixture(hash) {
  const listeners={},scrolls=[],anchors=[],frames=[],history=[];
  const node=id=>({id,listeners:{},addEventListener(type,fn){this.listeners[type]=fn;},
    closest:selector=>id==='modelCatalogEditor'&&selector==='#configurationModels'?{}:null,
    scrollIntoView:()=>anchors.push(id)});
  const nodes=Object.fromEntries(['configurationGeneralTab','configurationModelsTab','configurationGeneral','configurationModels','modelCatalogEditor','remediationTargets'].map(id=>[id,node(id)]));
  const env={document:{getElementById:id=>nodes[id]},location:{hash},
    history:{replaceState:(a,b,value)=>{history.push(value);env.location.hash=value;}},
    addEventListener:(type,fn)=>listeners[type]=fn,scrollTo:options=>scrolls.push(options.top),requestAnimationFrame:fn=>frames.push(fn),
    bootstrap:{Tab:{getOrCreateInstance:tab=>({show(){env.selected=tab.id;tab.listeners['shown.bs.tab']?.();}})}}};
  const controller=init(env);frames.forEach(fn=>fn());return {env,nodes,scrolls,anchors,history,controller,listeners};
}
test('general and model tab fragments are state, not DOM scroll targets on refresh',()=>{
  for(const hash of ['#general','#models','']) {
    const f=fixture(hash);assert.equal(f.env.selected,hash==='#models'?'configurationModelsTab':'configurationGeneralTab');
    assert.deepEqual(f.scrolls,[]);assert.deepEqual(f.anchors,[]);
    assert.equal(f.env.location.hash,hash==='#models'?'#models':'#general');
  }
});
test('old bookmarked panel URLs keep the right tab and undo their anchor jump',()=>{
  for(const hash of ['#configurationGeneral','#configurationModels','#modelCatalogEditor']) {
    const f=fixture(hash);assert.equal(f.env.location.hash,hash==='#configurationGeneral'?'#general':'#models');
    assert.deepEqual(f.scrolls,[0,0]);assert.deepEqual(f.anchors,[]);
    f.listeners.pageshow();assert.equal(f.scrolls.at(-1),0);
  }
});
test('changing tabs updates their non-anchor URL without scrolling or reloading',()=>{
  const f=fixture('#general');f.nodes.configurationModelsTab.listeners['shown.bs.tab']();
  assert.equal(f.env.location.hash,'#models');assert.deepEqual(f.scrolls,[]);assert.deepEqual(f.anchors,[]);
});
test('a genuine section deep link can still navigate to its content',()=>{
  const f=fixture('#remediationTargets');assert.deepEqual(f.anchors,['remediationTargets']);
});
