/* Read-only list filtering and selection state, shared by composition toolbars. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.WarpCombineLists = api;
})(typeof window === 'undefined' ? this : window, function () {
  function filterRows(rows, query) {
    const q = query.trim().toLowerCase();
    rows.forEach(row => { row.hidden = !(row.dataset.search || '').includes(q); });
  }
  function selectionState(all, boxes, count) {
    const visible = boxes.filter(box => !box.disabled && !box.closest('tr').hidden);
    const selected = boxes.filter(box => !box.disabled && box.checked).length;
    count.textContent = selected;
    all.checked = visible.length > 0 && visible.every(box => box.checked);
    all.indeterminate = visible.some(box => box.checked) && !all.checked;
    all.disabled = visible.length === 0;
    return selected;
  }
  function orderedRows(rows, descending = false) {
    return [...rows].sort((a, b) => (descending ? -1 : 1) *
      a.dataset.url.localeCompare(b.dataset.url, 'en', {numeric: true, sensitivity: 'base'}));
  }
  function availableSpace(viewport, top, padding = 24) {
    return Math.max(0, viewport - top - padding);
  }
  return { filterRows, selectionState, orderedRows, availableSpace };
});
