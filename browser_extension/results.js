/* Completion evidence is kept independently of the currently selected controls. */
const extensionResults = {
  async returnOriginal(item, tabs) {
    if (!item?.url || item.tabId == null || !['http:', 'https:'].includes(new URL(item.url).protocol))
      throw new Error('No original website is available.');
    const tab = await tabs.get(item.tabId);
    if (tab.url === item.url) {
      // Updating an unchanged URL need not navigate; reload the remote document.
      await tabs.reload(item.tabId, {bypassCache:true});
    } else {
      await tabs.update(item.tabId, {url:item.url});
    }
  },
  sourceUrl(tab, view) {
    return tab?.id === view?.tabId && tab?.url === view?.viewUrl ? view.url : tab?.url || '';
  },
  viewChange(tabId, change, view) {
    return tabId === view?.tabId && (!change.url || change.url === view.viewUrl);
  },
  evidence(data) {
    return {requestId:data.id, measurements:data.measurements || null,
      reportUrl:data.report_url || null,
      ...(data.configuration ? {config:data.configuration} : {})};
  },
  paint(item, locale, element) {
    const measurements = item?.measurements;
    element('completionScores').hidden = !measurements;
    if (!measurements) return;
    const format = value => typeof value === 'number' && Number.isFinite(value)
      ? new Intl.NumberFormat(locale, {maximumFractionDigits:2}).format(value) : '—';
    for (const metric of ['axe', 'lighthouse']) {
      element(`${metric}Original`).textContent = format(measurements.original?.[metric]);
      element(`${metric}Final`).textContent = format(measurements.final?.[metric]);
      const target = measurements.targets?.[metric];
      element(`${metric}Target`).textContent = target == null ? '—'
        : `${metric === 'axe' ? '≤' : '≥'} ${format(target)}`;
    }
    const report = element('completionReport');
    // Only link back to the configured local application, not arbitrary HTML.
    let safe = false;
    try { safe = new URL(item.reportUrl).origin === 'http://localhost'; } catch (_) {}
    report.hidden = !safe;
    if (safe) report.href = item.reportUrl;
  },
  async restore(item, requestId, fetcher, api) {
    if (item.measurements || !requestId) return item;
    const response = await fetcher(`${api}/requests/${requestId}`);
    if (!response.ok) return item;
    const data = await response.json();
    if (data.url !== item.url || data.status !== item.status || !data.measurements) return item;
    return {...item, ...this.evidence(data)};
  }
};
