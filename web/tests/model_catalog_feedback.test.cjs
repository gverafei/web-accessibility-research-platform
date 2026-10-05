const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

function fixture({lang='en',failure=false,delayed=false,models=[]}={}) {
  function element(tag='div') {return {tag,children:[],dataset:{},disabled:false,textContent:'',value:'',
    append(...items){this.children.push(...items);},replaceChildren(){this.children=[];},
    setAttribute(){},add(item){this.children.push(item);},focus(){this.focused=true;},scrollIntoView(){this.scrolled=true;}};}
  const ids=['modelCatalogEditor','modelCatalogRows','modelCatalogStatus','modelProviderPicker','providerModelSearch','providerModelResults','providerModelStatus','discoverModelsButton','closeProviderPicker','saveModelsButton'];
  const nodes=Object.fromEntries(ids.map(id=>[id,element()]));nodes.modelCatalogEditor.dataset.endpoint='/configuration/model-catalog';
  const notifications=[],requests=[],listeners={};let release;
  const choice={label:'Luna',model:'test/luna',tier:'low',color:'#2686c9',enabled:true,is_default:true};
  const context={document:{documentElement:{lang},getElementById:id=>nodes[id],createElement:element},
    Option:function(name,value){this.name=name;this.value=value;},crypto:{randomUUID:()=> 'test-id'},
    fetch:async (url,request)=>{requests.push({url,request});
      if(request?.method==='POST'&&delayed)await new Promise(done=>{release=done;});
      if(request?.method==='POST'&&failure)return {ok:false,status:400,json:async()=>({error:'Invalid model catalogue'})};
      return {ok:true,json:async()=>url.endsWith('/discover')?{models}:{choices:[{...choice}]}};
    },window:{addEventListener:(type,callback)=>listeners[type]=callback,
      warpButtonBusy:button=>{button.disabled=true;button.loading=true;return()=>{button.disabled=false;button.loading=false;};},
      warpNotify:(message,category)=>notifications.push({message,category})}};
  vm.runInNewContext(fs.readFileSync(require.resolve('../app/static/js/model_catalog_settings.js'),'utf8'),context);
  return {nodes,notifications,requests,listeners,release:()=>release()};
}
const tick=()=>new Promise(done=>setImmediate(done));
for(const lang of ['en','es'])test(`catalogue save uses the shared upper success notice (${lang}), not an inline success`,async()=>{
  const f=fixture({lang});await tick();await f.nodes.saveModelsButton.onclick();
  assert.equal(f.notifications[0].category,'success');
  assert.match(f.notifications[0].message,lang==='es'?/Catálogo de modelos guardado/:/Model catalogue saved/);
  assert.equal(f.nodes.modelCatalogStatus.textContent,'');assert.equal(f.nodes.saveModelsButton.disabled,false);
});
test('failed save retains edited choices and the unsaved guard, shows danger at top and unlocks the button',async()=>{
  const f=fixture({failure:true});await tick();const label=f.nodes.modelCatalogRows.children[0].children[1].children[0];
  label.value='Edited model';label.oninput();await f.nodes.saveModelsButton.onclick();
  assert.equal(f.notifications[0].category,'danger');assert.equal(f.notifications[0].message,'Invalid model catalogue');
  assert.equal(f.nodes.modelCatalogStatus.textContent,'Unsaved changes');assert.equal(label.value,'Edited model');
  assert.equal(f.nodes.saveModelsButton.disabled,false);let prevented=false;
  f.listeners.beforeunload({preventDefault:()=>{prevented=true;}});assert.equal(prevented,true);
});
test('pending catalogue save shows busy and prevents duplicate requests',async()=>{
  const f=fixture({delayed:true});await tick();const saving=f.nodes.saveModelsButton.onclick();
  assert.equal(f.nodes.saveModelsButton.loading,true);await f.nodes.saveModelsButton.onclick();
  assert.equal(f.requests.filter(item=>item.request?.method==='POST').length,1);
  f.release();await saving;assert.equal(f.nodes.saveModelsButton.loading,false);
});
test('provider discovery uses the same busy helper and makes no model-generation request',async()=>{
  const f=fixture();await tick();await f.nodes.discoverModelsButton.onclick();
  assert.equal(f.nodes.discoverModelsButton.loading,false);assert.equal(f.nodes.modelProviderPicker.hidden,false);
  assert.equal(f.nodes.modelProviderPicker.scrolled,true);assert.equal(f.nodes.providerModelSearch.focused,true);
  assert.equal(f.requests.at(-1).url,'/configuration/model-catalog/discover');assert.equal(f.notifications.length,0);
});
test('choosing a discovered model appends a visible unsaved choice without posting settings',async()=>{
  const f=fixture({models:[{model:'test/new-model',label:'New AI model',vision:true,reasoning_supported:true}]});
  await tick();await f.nodes.discoverModelsButton.onclick();f.nodes.providerModelResults.children[0].onclick();
  assert.equal(f.nodes.modelCatalogRows.children.length,2);
  const label=f.nodes.modelCatalogRows.children[1].children[1].children[0];assert.equal(label.value,'New AI model');
  assert.equal(f.nodes.modelCatalogStatus.textContent,'Unsaved changes');assert.equal(f.nodes.modelProviderPicker.hidden,true);
  assert.equal(f.requests.filter(item=>item.request?.method==='POST').length,0);
});
