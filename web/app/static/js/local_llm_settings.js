// Discover model capabilities from the researcher's external Ollama server.
(() => {
  const server = document.getElementById('ollama_base_url');
  const model = document.getElementById('ollama_model');
  const refresh = document.getElementById('refreshOllamaModels');
  const status = document.getElementById('ollamaModelsStatus');
  if (!server || !model || !refresh || !status) return;
  const placeholder = model.options[0].text;
  let pending = null;
  const load = async () => {
    pending?.abort();
    const address = server.value.trim();
    if (!address) {
      model.replaceChildren(new Option(placeholder, ''));
      status.textContent = '';
      refresh.disabled = false;
      return;
    }
    const selected = model.value;
    const controller = new AbortController();
    pending = controller;
    const timer = setTimeout(() => controller.abort(), 20000);
    refresh.disabled = true;
    status.textContent = '';
    try {
      const response = await fetch(refresh.dataset.modelsUrl, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({base_url: address}), signal: controller.signal,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || refresh.dataset.error);
      if (server.value.trim() !== address) return;
      model.replaceChildren(new Option(placeholder, ''));
      for (const item of data.models) model.add(new Option(item.name + ' · ' + (item.vision ? refresh.dataset.visionLabel : refresh.dataset.textLabel), item.id));
      if (data.models.some(item => item.id === selected)) model.value = selected;
      status.textContent = data.models.length ? '' : refresh.dataset.empty;
    } catch (error) {
      if (pending === controller) status.textContent = refresh.dataset.error;
    } finally {
      clearTimeout(timer);
      if (pending === controller) {
        refresh.disabled = false;
        pending = null;
      }
    }
  };
  server.addEventListener('change', load);
  refresh.addEventListener('click', load);
})();
