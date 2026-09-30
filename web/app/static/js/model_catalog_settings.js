/* Catalogue editing never mutates a recorded experiment or invokes a model. */
(() => {
  const root = document.getElementById('modelCatalogEditor');
  if (!root) return;
  const endpoint = root.dataset.endpoint, rows = document.getElementById('modelCatalogRows');
  const status = document.getElementById('modelCatalogStatus'), picker = document.getElementById('modelProviderPicker');
  const search = document.getElementById('providerModelSearch'), results = document.getElementById('providerModelResults');
  const es = document.documentElement.lang.startsWith('es');
  const say = (en, spanish) => es ? spanish : en;
  let choices = [], available = [], dirty = false;
  const showStatus = (message, state = 'info') => { status.textContent = message; status.dataset.state = state; };
  const element = (tag, text, cls) => { const n = document.createElement(tag); if (text) n.textContent = text; if (cls) n.className = cls; return n; };
  const changed = () => { dirty = true; showStatus(say('Unsaved changes', 'Cambios sin guardar'), 'unsaved'); };
  function select(values, selected, update) {
    const n = element('select', null, 'form-select form-select-sm');
    values.forEach(([value, name]) => n.add(new Option(name, value)));
    n.value = selected || ''; n.onchange = () => { update(n.value || null); changed(); }; return n;
  }
  function action(text, label, callback) {
    const n = element('button', text, 'btn btn-outline-secondary btn-sm');
    n.type = 'button'; n.title = label; n.setAttribute('aria-label', label); n.onclick = callback; return n;
  }
  function render() {
    rows.replaceChildren();
    choices.forEach((item, index) => {
      const tr = element('tr'), position = element('td', String(index + 1));
      const model = element('td');
      const label = element('input', null, 'form-control form-control-sm');
      label.value = item.label; label.maxLength = 120; label.setAttribute('aria-label', say('Model display name', 'Nombre del modelo'));
      label.oninput = () => { item.label = label.value; changed(); };
      model.append(label, element('small', item.model, 'text-muted d-block mt-1'));
      const tier = element('td'); tier.append(select([['low','Light'],['medium','Medium'],['high','High'],['xhigh','Extra high'],['max','Ultra']],item.tier,value => item.tier=value));
      const effort = element('td');
      const options = [['',say('Provider default / fixed','Predeterminado / fijo')]];
      if (item.reasoning_supported) options.push(...[['none','None'],['minimal','Minimal'],['low','Light'],['medium','Medium'],['high','High'],['xhigh','Extra high']]);
      effort.append(select(options,item.reasoning_effort,value => item.reasoning_effort=value));
      const color = element('td'), input = element('input', null, 'form-control form-control-color');
      input.type='color'; input.value=item.color; input.setAttribute('aria-label',say('Model color','Color del modelo'));
      input.oninput=()=>{item.color=input.value;changed();};color.append(input);
      const enabled = element('td'), toggle = element('input',null,'form-check-input');
      toggle.type='checkbox';toggle.checked=item.enabled;toggle.setAttribute('aria-label',say('Enabled model','Modelo habilitado'));
      toggle.onchange=()=>{item.enabled=toggle.checked;if(!item.enabled)item.is_default=false;changed();render();};enabled.append(toggle);
      const preferred=element('td'), radio=element('input',null,'form-check-input');
      radio.type='radio';radio.name='catalogDefault';radio.checked=!!item.is_default;radio.disabled=!item.enabled;
      radio.setAttribute('aria-label',say('Default model','Modelo predeterminado'));
      radio.onchange=()=>{choices.forEach(c=>c.is_default=c===item);changed();render();};preferred.append(radio);
      const actions=element('td'), buttons=element('div',null,'d-flex gap-1');
      const move=direction=>{const target=index+direction;if(target<0||target>=choices.length)return;[choices[index],choices[target]]=[choices[target],choices[index]];changed();render();};
      const up=action('↑',say('Move earlier','Mover antes'),()=>move(-1)), down=action('↓',say('Move later','Mover después'),()=>move(1));
      up.disabled=index===0;down.disabled=index===choices.length-1;
      buttons.append(up,down,action('×',say('Remove from slider','Quitar del slider'),()=>{choices.splice(index,1);changed();render();}));actions.append(buttons);
      tr.append(position,model,tier,effort,color,enabled,preferred,actions);rows.append(tr);
    });
  }
  async function jsonRequest(url, options) {
    const response=await fetch(url,options);let data;
    try{data=await response.json();}catch{throw new Error(say('The platform returned an invalid response.','La plataforma devolvió una respuesta inválida.'));}
    if(!response.ok)throw new Error(data.error||`HTTP ${response.status}`);return data;
  }
  function renderProvider() {
    const query=search.value.trim().toLowerCase();
    const matching=available.filter(m=>`${m.label} ${m.model}`.toLowerCase().includes(query));
    results.replaceChildren();
    matching.slice(0,60).forEach(item=>{
      const button=element('button',null,'model-provider-option');button.type='button';
      button.append(element('strong',item.label),element('small',item.model));
      const features=[item.vision?say('Text + images','Texto + imágenes'):say('Text','Texto'),item.reasoning_supported?say('Adjustable reasoning','Razonamiento configurable'):say('Fixed / default reasoning','Razonamiento fijo / predeterminado')];
      button.append(element('small',features.join(' · ')));
      button.onclick=()=>{if(choices.length>=32){showStatus(say('Maximum: 32 choices.','Máximo: 32 opciones.'), 'error');return;}
        choices.push({...item,id:`choice-${crypto.randomUUID()}`,enabled:true,is_default:false,tier:'high',reasoning_effort:null,color:'#2686c9'});changed();render();picker.hidden=true;};results.append(button);
    });
    if(!matching.length)results.append(element('p',say('No matching models.','Sin modelos coincidentes.')));
    else if(matching.length>60)results.append(element('p',say('Refine the search to see more models.','Afina la búsqueda para ver más modelos.')));
  }
  document.getElementById('discoverModelsButton').onclick=async()=>{
    picker.hidden=false;showStatus(say('Loading provider catalogue…','Cargando catálogo del proveedor…'));
    try{available=(await jsonRequest(`${endpoint}/discover`)).models;renderProvider();showStatus(say('Choose a model to add.','Selecciona un modelo para agregarlo.'));search.focus();}
    catch(error){showStatus(error.message, 'error');}
  };
  document.getElementById('closeProviderPicker').onclick=()=>picker.hidden=true;
  search.oninput=renderProvider;
  document.getElementById('saveModelsButton').onclick=async()=>{
    const button=document.getElementById('saveModelsButton');button.disabled=true;
    showStatus(say('Saving model catalogue…','Guardando catálogo de modelos…'));
    try{choices=(await jsonRequest(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({choices})})).choices;dirty=false;render();showStatus(say('✓ Model catalogue saved.','✓ Catálogo de modelos guardado.'), 'success');}
    catch(error){showStatus(error.message, 'error');}finally{button.disabled=false;}
  };
  window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
  jsonRequest(endpoint).then(data=>{choices=data.choices;render();}).catch(error=>showStatus(error.message, 'error'));
})();
