/* Both histories use the same records, controls and optional display preference. */
(function (root) {
  const key = 'history-list-view';
  function init(env = root) {
    const controls = [...env.document.querySelectorAll('[data-history-view-controls]')];
    let mode = 'table';
    try { if (env.localStorage.getItem(key) === 'cards') mode = 'cards'; } catch (_) {}
    function apply(next) {
      if (!['table', 'cards'].includes(next)) return;
      controls.forEach(control => {
        const view = env.document.getElementById(control.dataset.historyViewControls);
        if (!view) return;
        view.dataset.historyView = next;
        control.querySelectorAll('[data-history-mode]').forEach(button =>
          button.setAttribute('aria-pressed', String(button.dataset.historyMode === next)));
      });
    }
    apply(mode);
    controls.forEach(control => control.addEventListener('click', event => {
      const button = event.target.closest('[data-history-mode]');
      if (!button || !control.contains(button)) return;
      const next = button.dataset.historyMode;
      if (!['table', 'cards'].includes(next)) return;
      apply(next);
      try { env.localStorage.setItem(key, next); } catch (_) {}
    }));
  }
  if (typeof module === 'object' && module.exports) module.exports = {init};
  else init(root);
})(typeof window === 'object' ? window : globalThis);
