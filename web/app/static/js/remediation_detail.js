// Read-only report polling. Keep expanded evidence, focus and scroll position.
(() => {
  const active = node => ['queued', 'running'].includes(node?.dataset.runStatus);
  const key = detail => `${detail.closest('[data-iteration-id]')?.dataset.iterationId || 'run'}:${detail.dataset.reportPanel || detail.querySelector('summary')?.textContent.trim()}`;
  const previews = root => root.querySelectorAll('.page-preview').forEach(link => {
    const preview = link.querySelector('.page-preview-popover');
    if (!preview) return;
    const position = event => {
      const anchor = link.getBoundingClientRect(), margin = 16, gap = 18;
      const x = event.clientX ?? anchor.right, y = event.clientY ?? anchor.top;
      const rightSpace = window.innerWidth-x-gap-margin;
      const width = Math.min(600,window.innerWidth-2*margin,rightSpace>=180?rightSpace:Math.max(180,x-gap-margin));
      preview.style.width = `${width}px`;
      const left = rightSpace>=180?x+gap:Math.max(margin,x-gap-width);
      const height = preview.getBoundingClientRect().height;
      preview.style.setProperty('--preview-left',`${left}px`);
      preview.style.setProperty('--preview-top',`${Math.max(margin,Math.min(y,window.innerHeight-height-margin))}px`);
    };
    ['pointerenter','pointermove','focus'].forEach(event => link.addEventListener(event,position));
  });
  let root = document.getElementById('remediationReport');
  if (!root) return;
  previews(root);
  let controller;
  const refresh = async () => {
    if (!active(root)) return;
    if (!document.hidden && !document.getSelection()?.toString() &&
        !root.querySelector('input:focus,textarea:focus,select:focus,[contenteditable]:focus')) {
      controller = new AbortController();
      const deadline = setTimeout(() => controller.abort(), 15000);
      try {
        const url = new URL(window.location.href); url.searchParams.set('live','1');
        const response = await fetch(url, {signal: controller.signal, cache:'no-store', headers:{Accept:'text/html'}});
        if (!response.ok) throw new Error('Report refresh failed');
        const next = new DOMParser().parseFromString(await response.text(),'text/html').getElementById('remediationReport');
        if (!next || !next.dataset.runStatus) throw new Error('Incomplete report');
        const open = new Set(Array.from(root.querySelectorAll('details[open]'),key));
        const focused = document.activeElement?.closest('details');
        const focusKey = focused && root.contains(focused) ? key(focused) : null;
        const scroll = window.scrollY;
        next.querySelectorAll('details').forEach(detail => { detail.open = open.has(key(detail)); });
        root.replaceWith(next); root = next; previews(root);
        if (focusKey) Array.from(root.querySelectorAll('details')).find(detail => key(detail)===focusKey)?.querySelector('summary')?.focus({preventScroll:true});
        window.scrollTo({top:scroll,behavior:'instant'});
      } catch (_) {
        // Preserve the last valid report; temporary failures are retried.
      } finally { clearTimeout(deadline); }
    }
    if (active(root)) setTimeout(refresh,4000);
  };
  if (active(root)) setTimeout(refresh,4000);
  window.addEventListener('pagehide',() => controller?.abort(),{once:true});
})();
