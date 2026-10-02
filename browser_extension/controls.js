/* Read the same catalogue and intervention recipes as the web platform. */
const extensionControls = {
  catalog: null,
  async load(api) {
    const response = await fetch(`${api}/configuration`);
    if (!response.ok) throw new Error(`Platform configuration: HTTP ${response.status}`);
    const catalog = await response.json();
    if (!catalog.models?.length || catalog.preservation?.length !== 5)
      throw new Error('Invalid platform configuration.');
    this.catalog = catalog;
    const slider = document.getElementById('modelLevel');
    slider.max = String(catalog.models.length - 1);
    slider.value = String(Math.max(0, catalog.models.findIndex(m => m.id === catalog.default_model)));
    const dots = slider.nextElementSibling;
    dots.replaceChildren(...catalog.models.map(() => document.createElement('i')));
  },
  model(index) { return this.catalog?.models[index]; },
  paint(locale, modelIndex, preservationIndex) {
    const model = this.model(modelIndex);
    if (!model) return;
    const es = locale === 'es';
    const tiers = this.catalog.ui_copy?.[locale]?.tiers || {local:'Local', low:'Light', medium:'Medium', high:'High', xhigh:'Extra high', max:'Ultra'};
    document.getElementById('modelName').textContent = tiers[model.tier] || model.tier || model.name;
    document.getElementById('modelIdentity').textContent = model.name;
    document.getElementById('modelStep').value = `${modelIndex + 1} / ${this.catalog.models.length}`;
    document.querySelector('.slider-card.model').style.setProperty('--accent', model.color || '#2f9e66');
    document.getElementById('modelDetail').textContent = model.id.startsWith('ollama/')
      ? (es ? 'Modelo local configurado; sin sustitución por proveedores cloud.' : 'Configured local model; no cloud fallback.')
      : (es ? 'Modelo y razonamiento seleccionados explícitamente; se guardan con la corrida. Catálogo administrable en Configuración.' : 'Explicit model and reasoning selection, saved with the run. Manage the catalogue in Configuration.');
    const approach = this.catalog.preservation[preservationIndex];
    document.querySelector('.slider-card.preservation').style.setProperty('--accent', approach.color || '#6558c8');
    const text = this.catalog.ui_copy?.[locale];
    const presentation = text?.preservation[preservationIndex];
    document.getElementById('preservationName').textContent = presentation?.name || approach.name;
    document.getElementById('preservationSubtitle').textContent = presentation?.subtitle || '';
    document.getElementById('preservationDetail').textContent = presentation?.description || '';
    const r = approach.recipe;
    const labels = text?.labels || {temperature:'Temperature', iterations:'iterations', act:'ACT examples after failure', native:'Native / scoped components'};
    const framework = preservationIndex >= 3 ? 'Bootstrap 5.3.8' : labels.native;
    const act = document.getElementById('useRag').checked ? ` · ${r.rag_top_k}–12 ${labels.act}` : '';
    document.getElementById('recipe').textContent = `${presentation?.name || approach.name} · ${framework} · ${labels.temperature} ${Number(r.temperature).toFixed(2)} · ${r.iterations} ${labels.iterations} · Lighthouse ≥${r.lighthouse} · Axe ≤${r.axe}${act}.`;
  }
};
