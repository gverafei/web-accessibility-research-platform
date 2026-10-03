const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function results() {
  const context = vm.createContext({Intl, URL});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../results.js'),'utf8'),context);
  return vm.runInContext('extensionResults',context);
}

test('stored measured zeros, missing measurements and targets render distinctly', () => {
  const elements = new Map();
  const get = id => {if(!elements.has(id)) elements.set(id,{}); return elements.get(id);};
  const item = {measurements:{original:{axe:0,lighthouse:88},final:{axe:null,lighthouse:100},
    targets:{axe:0,lighthouse:94}},reportUrl:'http://localhost/remediation/647'};
  for(const locale of ['en','es']) {
    results().paint(item,locale,get);
    assert.equal(get('axeOriginal').textContent,'0');
    assert.equal(get('axeFinal').textContent,'—');
    assert.equal(get('axeTarget').textContent,'≤ 0');
    assert.equal(get('lighthouseFinal').textContent,'100');
    assert.equal(get('lighthouseTarget').textContent,'≥ 94');
    assert.equal(get('completionReport').href,item.reportUrl);
  }
  results().paint({},'en',get);
  assert.equal(get('completionScores').hidden,true);
  results().paint({...item,reportUrl:'https://example.org/'},'en',get);
  assert.equal(get('completionReport').hidden,true);
});

test('legacy completion backfill fetches its existing ID without running or applying again', async () => {
  const item = {url:'https://example.org/',status:'completed_with_warnings',message:'Applied',config:{rag:true}};
  const data = {id:3,url:item.url,status:item.status,measurements:{final:{axe:37,lighthouse:100}},report_url:'http://localhost/remediation/647'};
  let calls = 0;
  const restored = await results().restore(item,3,async url => {
    calls++; assert.equal(url,'http://localhost/api/browser-extension/requests/3');
    return {ok:true,json:async()=>data};
  },'http://localhost/api/browser-extension');
  assert.equal(calls,1); assert.equal(restored.message,'Applied');
  assert.equal(restored.requestId,3); assert.equal(restored.measurements.final.axe,37);
  await results().restore(restored,3,()=>{throw new Error('No second fetch');},'');
});

test('background completion persists scores even while the panel is closed', async () => {
  const completion = {id:3,status:'completed_with_warnings',message:'Finished',
    measurements:{original:{axe:169,lighthouse:88},final:{axe:37,lighthouse:100}},
    report_url:'http://localhost/remediation/647'};
  let saved;
  const context = vm.createContext({Intl, URL, Set, Date, fetch:async()=>({ok:true,json:async()=>completion}),
    importScripts:()=>{},chrome:{runtime:{onInstalled:{addListener(){}},onMessage:{addListener(){}},onStartup:{addListener(){}}},
      storage:{local:{get:async()=>({activeRequestId:3,runUrl:'https://example.org/',runTabId:null}),
        set:async value=>{saved=value;},remove:async()=>{}}},
      alarms:{create:async()=>{},clear:async()=>{},onAlarm:{addListener(){}}},notifications:{create(){}}}});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../results.js'),'utf8'),context);
  // Suppress only automatic startup; call the real background completion below.
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../service-worker.js'),'utf8').replace(/trackActiveRequest\(\);\s*$/,''),context);
  await vm.runInContext('finishRequest(3)',context);
  assert.equal(saved.lastCompletion.measurements.final.axe,37);
  assert.equal(saved.lastCompletion.reportUrl,completion.report_url);
  assert.equal(saved.completedRequestId,3);
});

test('cached completion injects the existing candidate without navigation or another experiment', async () => {
  const completion={id:3,status:'completed_with_warnings',candidate_url:'http://localhost/api/browser-extension/requests/3/candidate',
    measurements:{original:{axe:169,lighthouse:88},final:{axe:145,lighthouse:92}}};
  let saved, injected;
  const fetched=[];
  const context=vm.createContext({Intl,URL,Set,Date,fetch:async url=>{
    fetched.push(url);
    return url===completion.candidate_url?{ok:true,text:async()=>'<html>Stored candidate</html>'}:{ok:true,json:async()=>completion};
  },importScripts:()=>{},chrome:{
    runtime:{onInstalled:{addListener(){}},onMessage:{addListener(){}},onStartup:{addListener(){}}},
    storage:{local:{get:async()=>({activeRequestId:3,runTabId:9,runReused:true,locale:'en',runUrl:'https://example.org/'}),
        set:async value=>{if(value.lastCompletion)saved=value;},remove:async()=>{}}},
    tabs:{get:async()=>({url:'https://example.org/'}),update:async()=>{throw new Error('No navigation');}},
    scripting:{executeScript:async value=>{assert.equal(injected,undefined);injected=value;}},
    alarms:{clear:async()=>{},onAlarm:{addListener(){}}},notifications:{create(){}}}});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../results.js'),'utf8'),context);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../injection.js'),'utf8'),context);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../service-worker.js'),'utf8').replace(/trackActiveRequest\(\);\s*$/,''),context);
  await vm.runInContext('Promise.all([finishRequest(3),finishRequest(3)])',context);
  assert.deepEqual(fetched,['http://localhost/api/browser-extension/requests/3',completion.candidate_url]);
  assert.equal(injected.target.tabId,9);assert.equal(injected.world,'MAIN');
  assert.equal(injected.args[0],'<html>Stored candidate</html>');
  assert.equal(injected.args[1],'https://example.org/');
  assert.equal(saved.lastCompletion.viewUrl,'https://example.org/');
  assert.match(saved.lastCompletion.message,/keeping its address and origin/);
  assert.equal(saved.lastCompletion.reused,true);assert.equal(saved.lastCompletion.measurements.final.axe,145);
  assert.match(saved.lastCompletion.message,/Stored result recovered/);
});

test('temporary candidate address keeps original source identity and navigation is tab-specific',()=>{
  const view={tabId:9,url:'https://example.org/',viewUrl:'http://localhost/api/browser-extension/requests/3/candidate'};
  assert.equal(results().sourceUrl({id:9,url:view.viewUrl},view),view.url);
  assert.equal(results().sourceUrl({id:10,url:view.viewUrl},view),view.viewUrl);
  assert.equal(results().sourceUrl({id:9,url:'https://example.org/other'},view),'https://example.org/other');
  assert.equal(results().viewChange(9,{url:view.viewUrl},view),true);
  assert.equal(results().viewChange(9,{status:'loading'},view),true);
  assert.equal(results().viewChange(9,{url:'https://other.example/'},view),false);
  assert.equal(results().viewChange(10,{status:'loading'},view),false);
});

test('recovered completion uses frozen configuration instead of submitted RAG controls', () => {
  const data={id:12,configuration:{selectedModel:'anthropic/claude-opus-5.5',
    modelName:'Claude Opus 5.5 · Light reasoning',preservation:0,preservationName:'Minimal patches',rag:false}};
  const completion={config:{rag:true},...results().evidence(data)};
  assert.equal(completion.config.rag,false);
  assert.equal(completion.config.preservationName,'Minimal patches');
});

test('extension defaults to an accessible stored-result reuse switch', () => {
  const html=fs.readFileSync(path.join(__dirname,'../sidepanel.html'),'utf8');
  assert.match(html,/id="reuseResults" type="checkbox" role="switch" checked/);
  assert.match(html,/id="useRag" type="checkbox" role="switch"/);
  assert.match(html,/id="language" aria-label=/);
  assert.match(html,/id="theme" aria-label=/);
  const source=fs.readFileSync(path.join(__dirname,'../sidepanel.js'),'utf8');
  assert.match(source,/forceRerun=!\$\('reuseResults'\)\.checked/);
  assert.match(source,/force_rerun:forceRerun/);
});

test('compact options keep hidden preferences and numbering without explanatory paragraphs', () => {
  const html = fs.readFileSync(path.join(__dirname, '../sidepanel.html'), 'utf8');
  assert.match(html, /id="preferences" class="preferences" hidden/);
  assert.match(html, /id="preferencesButton".*aria-expanded="false" aria-controls="preferences"/);
  assert.match(html, /<legend><b>4<\/b> <span data-i18n="storedResultsTitle"/);
  assert.match(html, /<legend><b>3<\/b> <span data-i18n="optionalEvidence"/);
  assert.doesNotMatch(html, /id="(?:ragHelp|reuseHelp)"|aria-describedby="(?:ragHelp|reuseHelp)"/);
  assert.doesNotMatch(html, /header-preferences/);
});

test('return to unchanged original URL explicitly reloads the injected document', async () => {
  const calls=[];
  await results().returnOriginal({url:'https://example.org/',tabId:9},{
    get:async id=>{assert.equal(id,9);return {url:'https://example.org/'};},
    reload:async(id,options)=>calls.push([id,options.bypassCache]),
    update:async()=>{throw new Error('Same URL must reload');}
  });
  assert.deepEqual(calls,[[9,true]]);
});

test('return from a different URL navigates to the original source, not the candidate', async () => {
  const calls=[];
  await results().returnOriginal({url:'https://example.org/',tabId:9},{
    get:async()=>({url:'https://example.org/other'}),
    reload:async()=>{throw new Error('Different URL must navigate');},
    update:async(id,options)=>calls.push([id,options.url])
  });
  assert.deepEqual(calls,[[9,'https://example.org/']]);
  await assert.rejects(()=>results().returnOriginal({url:'blob:https://example.org/id',tabId:9},{}),/No original/);
});
