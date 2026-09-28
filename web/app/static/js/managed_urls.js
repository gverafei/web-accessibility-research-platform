/* Catalog paging stays on the server; this view owns only the visible rows. */
(() => {
  'use strict';
  const config = JSON.parse(document.getElementById('managedUrlConfig').textContent);
  const table = document.getElementById('urlCatalogTable'), body = table.tBodies[0];
  const filter = document.getElementById('urlCatalogFilter'), size = document.getElementById('urlPageSize');
  const loading = document.getElementById('urlCatalogLoading'), status = document.getElementById('urlPaginationStatus');
  const first = document.querySelector('.pager-first'), previous = document.querySelector('.pager-previous');
  const next = document.querySelector('.pager-next'), last = document.querySelector('.pager-last');
  let page = 1, pageCount = 1, sort = 'date', direction = 'desc', controller, debounce;

  async function load() {
    if (controller) controller.abort();
    const request = controller = new AbortController();
    // Reserve space before fetching; loading and image decoding must not move
    // the table or change the column widths between catalog pages.
    table.parentElement.style.minHeight = `${44 + Number(size.value) * 104}px`;
    loading.hidden = false; loading.textContent = config.loading;
    table.setAttribute('aria-busy', 'true');
    const params = new URLSearchParams({page, size: size.value, q: filter.value.trim(), sort, direction});
    try {
      const response = await fetch(config.dataUrl + '?' + params, {signal: request.signal, headers: {Accept: 'application/json'}});
      if (!response.ok) throw new Error(config.loadError);
      const data = await response.json();
      if (request !== controller) return;
      body.innerHTML = data.html;
      page = data.page; pageCount = data.page_count;
      status.textContent = `${config.page} ${page} ${config.of} ${pageCount} · ${data.total.toLocaleString('en-US')} ${config.rows}`;
      filter.nextElementSibling.textContent = filter.value.trim() ? `${data.total.toLocaleString('en-US')} ${config.matches}` : '';
      first.disabled = previous.disabled = page <= 1;
      next.disabled = last.disabled = page >= pageCount;
      const start = document.getElementById('startCategorization');
      start.textContent = '✦ ' + config.categorize + (data.uncategorized_count ? ` (${data.uncategorized_count.toLocaleString('en-US')})` : '');
      const available = [...document.getElementById('categoryModel').options].some(option => !option.disabled);
      start.disabled = !available || !data.uncategorized_count;
      loading.hidden = true;
    } catch (error) {
      if (error.name === 'AbortError') return;
      loading.textContent = config.loadError + ' ';
      const retry = document.createElement('button'); retry.className = 'btn btn-sm btn-outline-primary';
      retry.textContent = '↻'; retry.setAttribute('aria-label', config.loadError); retry.onclick = load;
      loading.append(retry);
    } finally {
      if (request === controller) table.setAttribute('aria-busy', 'false');
    }
  }
  filter.addEventListener('input', () => {clearTimeout(debounce); page = 1; debounce = setTimeout(load, 250);});
  size.addEventListener('change', () => {page = 1; load();});
  first.onclick = () => {page = 1; load();}; previous.onclick = () => {page--; load();};
  next.onclick = () => {page++; load();}; last.onclick = () => {page = pageCount; load();};
  table.querySelectorAll('.sort-button').forEach(button => button.onclick = () => {
    sort = button.dataset.column; direction = button.dataset.direction;
    table.querySelectorAll('.sort-button').forEach(item => {item.classList.remove('active'); item.querySelector('span').textContent = '↕';});
    button.classList.add('active'); button.querySelector('span').textContent = direction === 'asc' ? '↑' : '↓';
    button.dataset.direction = direction === 'asc' ? 'desc' : 'asc'; page = 1; load();
  });
  const endpoint = (url, id) => url.replace('/0/', '/' + id + '/');
  async function save(url, payload) {
    const response = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json', Accept: 'application/json'}, body: JSON.stringify(payload)});
    if (!response.ok) throw new Error(config.loadError);
    const data = await response.json(); return data;
  }
  body.addEventListener('click', event => {
    const row = event.target.closest('[data-result-id]'); if (!row) return;
    if (event.target.closest('.name-edit')) {
      const name = row.querySelector('[data-result-name]'), original = name.textContent.trim();
      name.contentEditable = 'true'; name.classList.add('editing'); name.focus();
      const finish = async commit => {
        if (!name.isContentEditable) return;
        name.contentEditable = 'false'; name.classList.remove('editing');
        if (!commit) {name.textContent = original; return;}
        try {const data = await save(endpoint(config.renameUrl, row.dataset.resultId), {display_name: name.textContent.trim()}); name.textContent = data.display_name;}
        catch (error) {name.textContent = original; await warpAlert(error.message);}
      };
      name.onkeydown = event => {if (event.key === 'Enter') {event.preventDefault(); finish(true);} else if (event.key === 'Escape') finish(false);};
      name.onblur = () => finish(false);
    }
    if (event.target.closest('.category-edit')) {
      const select = row.querySelector('.url-category-select'), line = row.querySelector('.url-category-line');
      line.hidden = true; select.hidden = false; select.focus();
      select.onblur = () => {select.hidden = true; line.hidden = false;};
      select.onchange = async () => {
        const category = row.querySelector('[data-site-category]'), original = category.textContent;
        try {const data = await save(endpoint(config.categoryUrl, row.dataset.resultId), {site_category: select.value}); category.textContent = data.site_category;}
        catch (error) {select.value = original; await warpAlert(error.message);}
        finally {select.hidden = true; line.hidden = false;}
      };
    }
  });
  const positionPreview = event => {
    const preview = event.target.closest('.matrix-page-preview'); if (!preview) return;
    const popover = preview.querySelector('.page-preview-popover');
    const place = () => {
      const rect = preview.getBoundingClientRect(), width = Math.min(540, window.innerWidth * .58);
      let left = rect.right + 12; if (left + width > window.innerWidth - 12) left = Math.max(12, rect.left - width - 12);
      popover.style.left = `${left}px`;
      const height = Math.min(popover.getBoundingClientRect().height || 540, window.innerHeight - 24);
      popover.style.top = `${Math.max(12, Math.min(rect.top, window.innerHeight - height - 12))}px`;
    };
    place(); requestAnimationFrame(place);
  };
  table.addEventListener('mouseover', positionPreview); table.addEventListener('focusin', positionPreview);
  load();
})();
