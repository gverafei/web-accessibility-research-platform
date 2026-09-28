/* Separate save scopes without discarding drafts when switching tabs. */
(() => {
  const general = document.getElementById('configurationGeneralTab');
  const models = document.getElementById('configurationModelsTab');
  if (!general || !models) return;
  const selectFromHash = () => {
    const hash = window.location.hash;
    const target = document.getElementById(hash.slice(1));
    const modelTab = hash === '#configurationModels' || target?.closest('#configurationModels');
    bootstrap.Tab.getOrCreateInstance(modelTab ? models : general).show();
    if (target) target.scrollIntoView({block: 'start'});
  };
  [general, models].forEach(tab => tab.addEventListener('shown.bs.tab', () => {
    // replaceState avoids reloads and does not fire hashchange recursively.
    history.replaceState(null, '', tab === models ? '#modelCatalogEditor' : '#configurationGeneral');
  }));
  window.addEventListener('hashchange', selectFromHash);
  selectFromHash();
})();
