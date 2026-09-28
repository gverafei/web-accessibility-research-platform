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
    document.getElementById('modelName').textContent = model.name;
    document.getElementById('modelStep').value = `${modelIndex + 1} / ${this.catalog.models.length}`;
    document.querySelector('.slider-card.model').style.setProperty('--accent', model.color || '#2f9e66');
    document.getElementById('modelDetail').textContent = model.id.startsWith('ollama/')
      ? (es ? 'Modelo local configurado; sin sustitución por proveedores cloud.' : 'Configured local model; no cloud fallback.')
      : (es ? 'Modelo y razonamiento seleccionados explícitamente; se guardan con la corrida. Catálogo administrable en Configuración.' : 'Explicit model and reasoning selection, saved with the run. Manage the catalogue in Configuration.');
    const approach = this.catalog.preservation[preservationIndex];
    document.querySelector('.slider-card.preservation').style.setProperty('--accent', approach.color || '#6558c8');
    const labels = es ? ['Parches mínimos', 'Reparación localizada', 'Reparación coordinada', 'Regeneración HTML', 'Regeneración Markdown'] : null;
    const descriptions = es ? [
      'Atributos, inserciones pequeñas y CSS acotado; sin reestructurar la página.',
      'Repara elementos defectuosos individuales, sin sustituir regiones completas.',
      'Coordina HTML, CSS y comportamiento de teclado local siguiendo causas y dependencias.',
      'Regenera desde el HTML adquirido con base Bootstrap y refina con parches; conserva el mejor candidato.',
      'Regenera desde Markdown verificado y el inventario de interfaz; refina con parches y conserva el mejor candidato.'
    ] : null;
    document.getElementById('preservationName').textContent = labels?.[preservationIndex] || approach.name;
    document.getElementById('preservationDetail').textContent = descriptions?.[preservationIndex] || approach.instruction;
    const r = approach.recipe;
    document.getElementById('recipe').textContent = `${es ? 'Contrato común' : 'Common contract'}: Lighthouse ≥${r.lighthouse} · Axe ≤${r.axe} · ${r.iterations} ${es ? 'iteraciones' : 'iterations'} · ≤$${r.cost} · ≤${r.seconds}s`;
  }
};
