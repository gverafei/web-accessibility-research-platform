/* Update only the visible list's active runs; leave filters and scroll intact. */
(function () {
  const table = document.querySelector('.remediation-history-table');
  if (!table) return;
  const input = document.getElementById('remediationListFilter');
  const count = document.getElementById('remediationFilterCount');
  const notice = document.getElementById('remediationLiveStatus');
  const rows = () => [...table.querySelectorAll('tbody tr[data-run-id]')];
  function filter() {
    const term = input.value.trim().toLocaleLowerCase();
    const current = rows();
    let visible = 0;
    current.forEach(row => {
      row.hidden = Boolean(term && !row.textContent.toLocaleLowerCase().includes(term));
      if (!row.hidden) visible++;
    });
    count.textContent = term ? `${visible} / ${current.length}` : '';
  }
  input.addEventListener('input', filter);
  async function refresh() {
    const active = rows().filter(row => ['queued', 'running'].includes(row.dataset.runStatus));
    if (!active.length) return;
    try {
      if (!document.hidden && !window.warpInteractionActive?.()) {
        for (let start = 0; start < active.length; start += 50) {
          const batch = active.slice(start, start + 50);
          const url = new URL(window.location.href);
          url.search = '';
          url.searchParams.set('live_ids', batch.map(row => row.dataset.runId).join(','));
          const response = await fetch(url, {cache:'no-store'});
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const page = new DOMParser().parseFromString(`<table><tbody>${await response.text()}</tbody></table>`, 'text/html');
          const updated = [...page.querySelectorAll('tr[data-run-id]')];
          for (const row of batch) {
            const replacement = updated.find(item => item.dataset.runId === row.dataset.runId);
            if (replacement) row.replaceWith(replacement);
          }
        }
        notice.hidden = true;
        filter();
      }
    } catch {
      notice.hidden = false; // Retry without dropping the last measured state.
    }
    window.setTimeout(refresh, 4000);
  }
  filter();
  window.setTimeout(refresh, 4000);
})();
