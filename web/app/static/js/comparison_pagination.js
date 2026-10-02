(function (root) {
    'use strict';
    function pageState(total, size, requested) {
        const pages = Math.max(1, Math.ceil(total / size));
        const page = Math.max(1, Math.min(requested, pages));
        return {page, pages, start:(page-1)*size, end:Math.min(page*size,total)};
    }
    function filterMembers(members, query) {
        const normalized = query.trim().toLocaleLowerCase();
        if (!normalized) return members;
        const matches = members.filter(member => member.text.toLocaleLowerCase().includes(normalized));
        const pairs = new Set(matches.map(member => member.pair).filter(Boolean));
        return members.filter(member => matches.includes(member) || (member.pair && pairs.has(member.pair)));
    }
    if (typeof module !== 'undefined') module.exports = {pageState, filterMembers};
    const pager = root.document?.getElementById('comparisonPagination');
    const body = root.document?.querySelector('#comparisonMembers tbody');
    if (!pager || !body) return;
    const size = pager.querySelector('select'), status = pager.querySelector('[aria-live]');
    const filter = root.document.getElementById('comparisonFilter');
    const filteredRows = () => filterMembers(Array.from(body.rows).map(row => {
        const pair = row.querySelector('[data-field="pair_key"] .inline-edit-label')?.textContent.trim() || '';
        const pairValue = row.querySelector('[data-field="pair_key"]')?.dataset.value ? pair : '';
        return {row, pair:pairValue, text:`${row.cells[1].textContent} ${pairValue}`};
    }), filter?.value || '').map(member => member.row);
    let page = 1;
    function render() {
        const allRows = Array.from(body.rows), rows = filteredRows(), state = pageState(rows.length, Number(size.value), page);
        page = state.page;
        allRows.forEach(row => {row.hidden=true;});
        rows.forEach((row,i) => {row.hidden = i < state.start || i >= state.end;});
        status.textContent = `${pager.dataset.pageLabel} ${page} ${pager.dataset.ofLabel} ${state.pages} · ${rows.length}`;
        pager.querySelectorAll('[data-page-action]').forEach(button => {
            button.disabled = ['first','previous'].includes(button.dataset.pageAction) ? page===1 : page===state.pages;
        });
    }
    pager.querySelectorAll('[data-page-action]').forEach(button => button.addEventListener('click', () => {
        const action = button.dataset.pageAction;
        page = action==='first'?1:action==='last'?Math.max(1,Math.ceil(filteredRows().length/Number(size.value))):page+(action==='next'?1:-1);
        render();
    }));
    size.addEventListener('change', () => {page=1; render();});
    filter?.addEventListener('input', () => {page=1; render();});
    new root.MutationObserver(render).observe(body,{childList:true,subtree:true,characterData:true});
    render();
})(typeof window !== 'undefined' ? window : globalThis);
