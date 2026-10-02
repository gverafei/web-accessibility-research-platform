const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

async function finish({candidateUrl='http://localhost/api/browser-extension/requests/3/candidate',
  tabUrl='https://example.org/',candidateView=null,injectionError=false,candidateError=false}={}) {
  let completion;
  const updates=[],injections=[];
  const context=vm.createContext({Intl,URL,Set,Date,importScripts(){},
    fetch:async url=>url===candidateUrl?{ok:!candidateError,status:404,text:async()=>'<html><body>Stored</body></html>'}:
      {ok:true,json:async()=>({id:3,status:'accepted',candidate_url:candidateUrl})},
    chrome:{runtime:{onInstalled:{addListener(){}},onMessage:{addListener(){}},onStartup:{addListener(){}}},
      storage:{local:{get:async()=>({activeRequestId:3,runTabId:9,runUrl:'https://example.org/',candidateView,locale:'en'}),
        set:async value=>{if(value.lastCompletion)completion=value.lastCompletion;},remove:async()=>{}}},
      tabs:{get:async()=>({url:tabUrl}),update:async(id,value)=>{
        updates.push({id,...value});}},
      scripting:{executeScript:async value=>{injections.push(value);if(injectionError)throw new Error('Tab closed');}},
      alarms:{clear:async()=>{},onAlarm:{addListener(){}}},notifications:{create(){}}}});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../results.js'),'utf8'),context);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../injection.js'),'utf8'),context);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../service-worker.js'),'utf8')
    .replace(/trackActiveRequest\(\);\s*$/,''),context);
  await vm.runInContext('finishRequest(3)',context);
  return {completion,updates,injections};
}

test('delivery cannot navigate to a supplied external, blob or unrelated localhost URL',async()=>{
  for(const candidateUrl of ['https://example.org/candidate','blob:https://example.org/candidate',
    'http://localhost/settings','http://localhost/api/browser-extension/requests/4/candidate',
    'http://localhost:8080/api/browser-extension/requests/3/candidate']) {
    const {completion,updates}=await finish({candidateUrl});
    assert.equal(updates.length,0);assert.equal(completion.viewUrl,null);
    assert.match(completion.message,/could not be applied/);
  }
});

test('changed-origin tab is left alone, including the previous mapped localhost view',async()=>{
  assert.equal((await finish({tabUrl:'https://other.example/'})).injections.length,0);
  const view={tabId:9,url:'https://example.org/',viewUrl:'http://localhost/api/browser-extension/requests/2/candidate'};
  const {completion,updates,injections}=await finish({tabUrl:view.viewUrl,candidateView:view});
  assert.equal(updates.length,0);assert.equal(injections.length,0);assert.equal(completion.url,view.url);
});

test('script application failure retains completion without a navigation fallback',async()=>{
  const {completion,updates}=await finish({injectionError:true});
  assert.equal(completion.viewUrl,null);assert.equal(completion.status,'accepted');
  assert.match(completion.message,/could not be applied: Tab closed/);
  assert.equal(updates.length,0);
});

test('unavailable stored HTML cannot be injected',async()=>{
  const {completion,injections}=await finish({candidateError:true});
  assert.equal(injections.length,0);assert.equal(completion.viewUrl,null);
  assert.match(completion.message,/Candidate HTTP 404/);
});

test('extension delivery has no iframe, blob factory or localhost navigation',()=>{
  const worker=fs.readFileSync(path.join(__dirname,'../service-worker.js'),'utf8');
  const panel=fs.readFileSync(path.join(__dirname,'../sidepanel.js'),'utf8');
  assert.doesNotMatch(worker+panel,/createObjectURL|createElement\(['"]iframe|\.srcdoc\s*=/);
  assert.doesNotMatch(worker,/chrome\.tabs\.update\(/);
  const manifest=JSON.parse(fs.readFileSync(path.join(__dirname,'../manifest.json'),'utf8'));
  assert.equal(manifest.permissions.includes('scripting'),true);
});
