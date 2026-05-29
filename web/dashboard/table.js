/* EigenEdge dashboard — controller.
   View state, rendering, popovers, saved views, favorites, undo, scan wiring. No caps. */

window.EV_APP = (() => {
  const F = window.EV_FILTERS, V = window.EV_VIEWS, D = window.EV_DATA;
  const $ = id => document.getElementById(id);

  let DATA = { daily: [], week: [], all: [], regime: null, todaySet: new Set(), errors: [] };
  const S = {
    mode: 'daily', search: '', chips: [], sets: { conv: [], ta: [], gex: [] },
    numeric: {}, favsOnly: false,
    cols: F.defaultVisible(), sort: [{ key: 'conv', dir: 'desc' }], selTk: null,
  };
  const undoStack = [];

  const fmtPrice = n => n == null ? '—' : (Math.abs(n) >= 100 ? n.toFixed(0) : n.toFixed(2));
  const pct = n => Math.round((n || 0) * 100);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  // ---------- state snapshot / undo ----------
  function snap() {
    return JSON.stringify({ mode: S.mode, search: S.search, chips: S.chips, sets: S.sets, numeric: S.numeric, favsOnly: S.favsOnly, cols: S.cols, sort: S.sort });
  }
  function persist() { V.saveUI(JSON.parse(snap())); }
  function mutate(fn) { undoStack.push(snap()); if (undoStack.length > 60) undoStack.shift(); fn(); persist(); renderAll(); }
  function undo() {
    if (!undoStack.length) return;
    const prev = JSON.parse(undoStack.pop());
    Object.assign(S, prev);
    $('searchInput').value = S.search || '';
    persist(); renderAll();
  }

  // ---------- data shaping ----------
  function modeRows(m) { return m === 'daily' ? DATA.daily : m === 'week' ? DATA.week : DATA.all; }
  function filtered(m) {
    return F.apply(modeRows(m), { ...S, favs: new Set(V.getFavs()) });
  }
  function displayCols() {
    return F.COLUMNS.filter(c => c.weekOnly ? S.mode === 'week' : S.cols.includes(c.key));
  }
  function sortVal(col, row) {
    if (col.key === 'fresh') return row.fresh ? 1 : 0;
    if (col.key === 'ta') return ({ HIGH: 2, SPEC: 1 })[row.taTier] || 0;
    if (col.key === 'gex') return ({ run: 3, flip: 2, pin: 1 })[row.gexKey] || 0;
    return col.get(row);
  }
  function cmpVals(a, b) {
    if (a == null && b == null) return 0;
    if (a == null) return 1; if (b == null) return -1;
    if (typeof a === 'string' || typeof b === 'string') return String(a).localeCompare(String(b));
    return a - b;
  }
  function sortRows(rows) {
    const favs = new Set(V.getFavs());
    return [...rows].sort((a, b) => {
      const fa = favs.has(a.ticker), fb = favs.has(b.ticker);
      if (fa !== fb) return fa ? -1 : 1;
      if (S.mode !== 'daily') {
        const ta = DATA.todaySet.has(a.ticker), tb = DATA.todaySet.has(b.ticker);
        if (ta !== tb) return ta ? -1 : 1;
      }
      for (const s of S.sort) {
        const col = F.COL_BY_KEY[s.key]; if (!col) continue;
        const c = cmpVals(sortVal(col, a), sortVal(col, b));
        if (c) return s.dir === 'asc' ? c : -c;
      }
      return 0;
    });
  }

  // ---------- regime ----------
  function renderRegime() {
    const el = $('regimeBar'); const r = DATA.regime;
    const brand = `<div class="reg-brand"><span class="logo-mark">◢◣</span> Eigen<em>Edge</em></div>`;
    if (!r || r.regime === 'UNKNOWN' || r.regime == null) {
      const msg = (r && r.narrative) ? r.narrative : 'No macro data — run Refresh Data.';
      el.innerHTML = `<div class="reg-badge u"><span class="reg-lbl">Regime</span><span class="reg-val">— / 10</span></div><div class="regime-empty">${esc(msg)}</div><div class="ab-spacer"></div>${brand}`;
      return;
    }
    const tone = r.score >= 7 ? 'g' : r.score >= 3 ? 'a' : 'r';
    const cells = [];
    if (r.gex_index != null) cells.push({ k: 'SPX GEX', v: `$${(Math.abs(r.gex_index) / 1e9).toFixed(1)}B`, t: r.gex_index > 0 ? 'g' : 'r' });
    if (r.vix_contango_pct != null) cells.push({ k: 'VIX TERM', v: r.vix_contango_pct > 0 ? 'Contango' : 'Backwrd', t: r.vix_contango_pct > 0 ? 'g' : 'r' });
    if (r.dix != null) cells.push({ k: 'DIX', v: `${(r.dix * 100).toFixed(1)}%`, t: r.dix > 0.43 ? 'g' : 'a' });
    if (r.vix_m1 != null) cells.push({ k: 'VIX', v: r.vix_m1.toFixed(1), t: r.vix_m1 < 20 ? 'g' : r.vix_m1 > 30 ? 'r' : 'a' });
    el.innerHTML = `
      <div class="reg-badge ${tone}"><span class="reg-lbl">Regime · ${esc(r.date || '')}</span><span class="reg-val">${esc(r.regime)} ${r.score}/10</span></div>
      <div class="reg-cells">${cells.map(c => `<div class="reg-cell ${c.t}"><span class="rc-k">${c.k}</span><span class="rc-v">${esc(c.v)}</span></div>`).join('')}</div>
      ${brand}
      <div class="reg-narr">${esc(r.narrative || '')}</div>`;
  }

  // ---------- tabs ----------
  function renderTabs() {
    const counts = { daily: filtered('daily').length, week: filtered('week').length, all: filtered('all').length };
    const tab = (m, lbl) => `<button class="mode ${S.mode === m ? 'on' : ''}" data-mode="${m}">${lbl} <span class="mc">${counts[m]}</span></button>`;
    $('modeTabs').innerHTML = tab('daily', 'DAILY') + tab('week', 'WEEKLY') + tab('all', 'ALL');
  }

  // ---------- chip + set-dropdown row ----------
  function renderChips() {
    const chips = F.CHIPS.map(c => {
      const on = S.chips.includes(c.id);
      return `<button class="chip ${on ? 'on' : ''}" data-chip="${c.id}">${on ? '✓ ' : ''}${c.label}</button>`;
    }).join('');
    const setBtn = (name) => {
      const sel = S.sets[name] || [];
      const on = sel.length > 0;
      return `<button class="chip setbtn ${on ? 'on' : ''}" data-set="${name}">${F.SETS[name].label} ${on ? `(${sel.length})` : ''} ▾</button>`;
    };
    const favOn = S.favsOnly ? 'on' : '';
    $('chipRow').innerHTML =
      `<button class="iconbtn" id="filtersToggle">Filters ▾</button>` +
      chips + setBtn('conv') + setBtn('ta') + setBtn('gex') +
      `<button class="chip ${favOn}" id="favsOnlyChip">★ FAVS ONLY</button>` +
      `<button class="chip clear" id="clearAll">CLEAR</button>`;
  }

  // ---------- table ----------
  function renderTable() {
    const host = $('tableHost');
    const cols = displayCols();
    const rows = sortRows(filtered(S.mode));

    if (DATA.errors.length && !DATA.daily.length && !DATA.week.length && !DATA.all.length) {
      host.innerHTML = `<div class="tablecard"><div class="empty"><div class="empty-i">⚠</div><div><b>Can't reach the API.</b><br>${esc(DATA.errors.join(' · '))}</div></div></div>`;
      return;
    }
    if (!rows.length) {
      const why = modeRows(S.mode).length ? 'No rows match the current search / filters.' :
        (S.mode === 'all' ? 'No scanned tickers for today yet — hit SCAN.' : `No ${S.mode === 'daily' ? 'picks today' : 'picks this week'} yet — hit SCAN.`);
      host.innerHTML = `<div class="tablecard"><div class="empty"><div class="empty-i">∅</div><div>${esc(why)}</div></div></div>`;
      return;
    }

    const sortIdx = k => S.sort.findIndex(s => s.key === k);
    const head = cols.map(c => {
      const i = sortIdx(c.key);
      const arrow = i >= 0 ? (S.sort[i].dir === 'asc' ? ' ↑' : ' ↓') : '';
      const rank = (i >= 0 && S.sort.length > 1) ? `<span class="sort-rank">${i + 1}</span>` : '';
      const funnel = c.numeric ? `<span class="th-funnel ${S.numeric[c.key] ? 'on' : ''}" data-funnel="${c.key}" title="Range filter">⏷</span>` : '';
      return `<th class="${c.align === 'c' ? 'c' : ''} ${i >= 0 ? 'sort' : ''} col-${c.key}" data-sort="${c.key}">${esc(c.label)}${arrow}${rank}${funnel}</th>`;
    }).join('');

    let lastDate = null;
    const body = rows.map(r => {
      let grp = '';
      if (S.mode === 'week' && r.date !== lastDate) {
        lastDate = r.date;
        grp = `<tr class="date-grp"><td colspan="${cols.length}">${esc(r.date || '—')}</td></tr>`;
      }
      const isToday = DATA.todaySet.has(r.ticker);
      const dirCls = r.dir === 'short' ? 'short' : 'long';
      const cells = cols.map(c => cell(c, r, isToday)).join('');
      return grp + `<tr class="${S.selTk === r.ticker ? 'sel' : ''} ${isToday ? 'today' : ''} ${dirCls}" data-tk="${esc(r.ticker)}">${cells}</tr>`;
    }).join('');

    const tot = { d: DATA.daily.length, w: DATA.week.length, a: DATA.all.length };
    host.innerHTML = `<div class="tablecard"><table class="dtable">
      <thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>
      <div class="table-foot">${rows.length} shown · ${tot.d} daily · ${tot.w} weekly · ${tot.a} matrix · NO CAP</div></div>`;
  }

  function cell(c, r, isToday) {
    const cls = `class="${c.align === 'c' ? 'c' : ''} col-${c.key}"`;
    switch (c.kind) {
      case 'ticker': {
        const on = V.isFav(r.ticker) ? 'on' : '';
        return `<td ${cls}><div class="tk"><span class="star ${on}" data-fav="${esc(r.ticker)}">★</span><span class="sym">${esc(r.ticker)}</span>${isToday ? `<span class="today-dot">●</span>` : ''}</div></td>`;
      }
      case 'dir': return `<td ${cls}><span class="dir-tag ${r.dir}">${esc(r.dir.toUpperCase())}</span></td>`;
      case 'conv': return `<td ${cls}><span class="conv-bar">${Array.from({ length: 5 }, (_, i) => `<span class="cv ${i < (r.conv || 0) ? 'on' : ''}"></span>`).join('')}</span></td>`;
      case 'tatier': return `<td ${cls}>${r.taTier ? `<span class="pill ta-${r.taTier.toLowerCase()}">${r.taTier}</span>` : '<span class="muted">—</span>'}</td>`;
      case 'gexpill': return `<td ${cls}>${r.gexKey ? `<span class="pill gx-${r.gexCls}">${esc(r.gexLabel)}</span>` : '<span class="muted">—</span>'}</td>`;
      case 'fbar': { const v = c.get(r); return `<td ${cls}><span class="fbar"><span class="fb-fill" style="width:${pct(v)}%"></span></span><span class="fnum">${v ? pct(v) : ''}</span></td>`; }
      case 'fresh': return `<td ${cls}>${r.fresh ? '<span class="fresh-yes">✓</span>' : ''}</td>`;
      case 'tv': return `<td ${cls}><a class="tv-link" href="${D.tvLink(r)}" target="_blank" rel="noopener" data-tv="1">↗</a></td>`;
      case 'price': { const v = c.get(r); return `<td ${cls}><span class="price">${v == null ? '—' : '$' + fmtPrice(v)}</span></td>`; }
      case 'entry': return `<td ${cls}><span class="price">${r.entryLow == null ? '—' : '$' + fmtPrice(r.entryLow) + '–' + fmtPrice(r.entryHigh)}</span></td>`;
      default: { const v = c.get(r); return `<td ${cls}><span class="price">${esc(v == null || v === '' ? '—' : v)}</span></td>`; }
    }
  }

  // ---------- action bar ----------
  function findRow(tk) {
    return DATA.daily.find(r => r.ticker === tk) || DATA.week.find(r => r.ticker === tk) || DATA.all.find(r => r.ticker === tk);
  }
  function selectRow(tk) {
    const bar = $('actionBar');
    if (S.selTk === tk && bar.classList.contains('open')) { closeBar(); return; }
    S.selTk = tk; renderTable();
    const r = findRow(tk); if (!r) return;
    bar.classList.add('open');
    const stat = (lbl, val, k = '') => `<div class="ab-stat"><span>${lbl}</span><b class="${k}">${val}</b></div>`;
    bar.innerHTML = `
      <button class="ab-close" id="abClose">×</button>
      <div class="ab-main">
        <div class="ab-act ${r.dir}">${r.dir === 'short' ? '● SHORT' : '● BUY'} ${esc(r.ticker)}</div>
        ${r.entryLow != null ? stat('Entry', `$${fmtPrice(r.entryLow)}–$${fmtPrice(r.entryHigh)}`) : ''}
        ${r.stop != null ? stat('Stop', `$${fmtPrice(r.stop)}`, 'r') : ''}
        ${r.target != null ? stat('Target', `$${fmtPrice(r.target)}`, 'g') : ''}
        ${r.price != null ? stat('Price', `$${fmtPrice(r.price)}`) : ''}
        ${stat('GEX', r.gexKey ? esc(r.gexLabel) : '—')}
        ${stat('Call Wall', r.callWall != null ? '$' + fmtPrice(r.callWall) : '—', 'g')}
        ${stat('Put Wall', r.putWall != null ? '$' + fmtPrice(r.putWall) : '—', 'r')}
        ${stat('TA', r.taTier || '—')}
        ${stat('Setup', r.setup || '—')}
        ${stat('Conv', (r.conv || 0) + '/5')}
        <div class="ab-spacer"></div>
        <a class="ab-tv" href="${D.tvLink(r)}" target="_blank" rel="noopener">↗ Open in TradingView</a>
      </div>
      ${r.thesis ? `<div class="ab-thesis">${esc(r.thesis)}</div>` : ''}`;
    $('abClose').onclick = closeBar;
  }
  function closeBar() { $('actionBar').classList.remove('open'); S.selTk = null; renderTable(); }

  // ---------- popovers ----------
  function openPop(html, rect) {
    const layer = $('popLayer'); layer.classList.add('on');
    const old = layer.querySelector('.pop'); if (old) old.remove();
    const pop = document.createElement('div'); pop.className = 'pop'; pop.innerHTML = html;
    layer.appendChild(pop);
    const w = pop.offsetWidth || 240;
    let left = rect.left; if (left + w > window.innerWidth - 8) left = window.innerWidth - w - 8;
    pop.style.left = Math.max(8, left) + 'px'; pop.style.top = (rect.bottom + 6) + 'px';
    return pop;
  }
  function closePop() { const l = $('popLayer'); l.classList.remove('on'); const p = l.querySelector('.pop'); if (p) p.remove(); }

  function openSetMenu(name, rect) {
    const def = F.SETS[name]; const sel = S.sets[name] || [];
    const html = `<h4>${esc(def.label)}</h4>` + def.options.map(o =>
      `<label class="pop-row"><input type="checkbox" data-opt="${esc(o.v)}" ${sel.includes(o.v) ? 'checked' : ''}/>${esc(o.label)}</label>`).join('') +
      `<div class="pop-btns"><button class="pop-btn" id="setClear">Clear</button></div>`;
    const pop = openPop(html, rect);
    pop.addEventListener('change', e => {
      const v = e.target.dataset.opt; if (v == null) return;
      const cur = new Set(S.sets[name] || []);
      // checkbox values may be numbers (conv)
      const val = name === 'conv' ? Number(v) : v;
      mutate(() => { if (e.target.checked) cur.add(val); else cur.delete(val); S.sets[name] = [...cur]; });
    });
    pop.querySelector('#setClear').onclick = () => mutate(() => { S.sets[name] = []; });
  }

  function openCols(rect) {
    const html = `<h4>Columns</h4>` + F.COLUMNS.filter(c => !c.weekOnly && c.key !== 'tv').map(c =>
      `<label class="pop-row"><input type="checkbox" data-col="${c.key}" ${S.cols.includes(c.key) ? 'checked' : ''}/>${esc(c.label)}</label>`).join('');
    const pop = openPop(html, rect);
    pop.addEventListener('change', e => {
      const k = e.target.dataset.col; if (!k) return;
      mutate(() => { if (e.target.checked) { if (!S.cols.includes(k)) S.cols.push(k); } else S.cols = S.cols.filter(x => x !== k); });
    });
  }

  function openNumeric(key, rect) {
    const col = F.COL_BY_KEY[key]; const cur = S.numeric[key] || {};
    const html = `<h4>Filter · ${esc(col.label)}</h4>
      <div class="pop-num"><input id="nmin" type="number" placeholder="min" value="${cur.min ?? ''}"/><input id="nmax" type="number" placeholder="max" value="${cur.max ?? ''}"/></div>
      <div class="pop-btns"><button class="pop-btn" id="nclear">Clear</button><button class="pop-btn go" id="napply">Apply</button></div>`;
    const pop = openPop(html, rect);
    pop.querySelector('#napply').onclick = () => {
      const mn = pop.querySelector('#nmin').value, mx = pop.querySelector('#nmax').value;
      mutate(() => { if (mn === '' && mx === '') delete S.numeric[key]; else S.numeric[key] = { min: mn === '' ? null : +mn, max: mx === '' ? null : +mx }; });
      closePop();
    };
    pop.querySelector('#nclear').onclick = () => { mutate(() => { delete S.numeric[key]; }); closePop(); };
  }

  function openViewMenu(rect) {
    const views = V.getViews();
    const html = `<h4>Saved Views</h4>` + (views.length ? views.map(v =>
      `<div class="pop-row" data-view="${esc(v.name)}">${esc(v.name)}${v.builtin ? '<span class="view-builtin">DEFAULT</span>' : ''}<span class="meta">${esc(v.mode)}</span>${v.builtin ? '' : `<span class="pop-del" data-delview="${esc(v.name)}">✕</span>`}</div>`).join('')
      : `<div class="pop-row">No saved views.</div>`);
    const pop = openPop(html, rect);
    pop.addEventListener('click', e => {
      const del = e.target.dataset.delview, row = e.target.closest('[data-view]');
      if (del) { e.stopPropagation(); V.deleteView(del); openViewMenu(rect); return; }
      if (row) { closePop(); applyView(V.getView(row.dataset.view)); }
    });
  }

  function saveViewModal() {
    const m = $('modal'); m.classList.add('on');
    const views = V.getViews();
    const cur = S._viewName || '';   // default to current view name if loaded from one
    m.innerHTML = `<div class="modal-box"><h3>Save view</h3>
      <input id="viewName" placeholder="View name…" autocomplete="off" value="${esc(cur)}" list="viewNames"/>
      <datalist id="viewNames">${views.map(v => `<option value="${esc(v.name)}"></option>`).join('')}</datalist>
      <div class="pop-btns"><button class="pop-btn" id="vCancel">Cancel</button><button class="pop-btn go" id="vSave">Save</button></div></div>`;
    const inp = $('viewName'); inp.focus(); inp.select();
    const close = () => { m.classList.remove('on'); m.innerHTML = ''; };
    $('vCancel').onclick = close;
    $('vSave').onclick = () => {
      const name = inp.value.trim(); if (!name) { inp.focus(); return; }
      // overwrite without confirmation (existing name just replaces)
      V.saveView({ name, mode: S.mode, search: S.search, chips: [...S.chips], sets: JSON.parse(JSON.stringify(S.sets)), numeric: { ...S.numeric }, cols: [...S.cols], sort: [...S.sort], favsOnly: S.favsOnly });
      S._viewName = name;
      close();
    };
    inp.onkeydown = e => { if (e.key === 'Enter') $('vSave').click(); if (e.key === 'Escape') close(); };
  }

  function applyView(v) {
    if (!v) return;
    mutate(() => {
      S.mode = v.mode || 'daily';
      S.search = v.search || ''; $('searchInput').value = S.search;
      S.chips = [...(v.chips || [])];
      S.sets = v.sets ? JSON.parse(JSON.stringify(v.sets)) : { conv: [], ta: [], gex: [] };
      if (!S.sets.conv) S.sets.conv = []; if (!S.sets.ta) S.sets.ta = []; if (!S.sets.gex) S.sets.gex = [];
      S.numeric = { ...(v.numeric || {}) };
      S.cols = v.cols ? [...v.cols] : F.defaultVisible();
      S.sort = v.sort ? v.sort.map(s => ({ ...s })) : [{ key: 'conv', dir: 'desc' }];
      S.favsOnly = !!v.favsOnly;
      S._viewName = v.name;
    });
  }

  // ---------- sorting ----------
  function clickSort(key, shift) {
    const i = S.sort.findIndex(s => s.key === key);
    const isText = ['ticker', 'dir', 'setup', 'date'].includes(key);
    mutate(() => {
      if (shift) {
        if (i >= 0) S.sort[i].dir = S.sort[i].dir === 'asc' ? 'desc' : 'asc';
        else S.sort.push({ key, dir: isText ? 'asc' : 'desc' });
      } else {
        if (i === 0 && S.sort.length === 1) S.sort[0].dir = S.sort[0].dir === 'asc' ? 'desc' : 'asc';
        else S.sort = [{ key, dir: isText ? 'asc' : 'desc' }];
      }
    });
  }

  function updateFavCount() { $('favCount').textContent = V.getFavs().length; }

  function renderAll() { renderRegime(); renderTabs(); renderChips(); renderTable(); updateFavCount(); }

  // ---------- data load ----------
  async function reload() {
    DATA = await D.loadAll();
    if (S.selTk && !findRow(S.selTk)) closeBar();
    renderAll();
  }
  // light reload during scan: refresh data + table without disturbing open popovers/inputs
  async function liveReload() {
    try { DATA = await D.loadAll(); renderTabs(); renderTable(); } catch {}
  }

  // ---------- wiring ----------
  function wire() {
    $('modeTabs').addEventListener('click', e => { const b = e.target.closest('[data-mode]'); if (!b) return; closeBar(); mutate(() => { S.mode = b.dataset.mode; }); });

    const si = $('searchInput');
    si.addEventListener('input', () => { S.search = si.value; persist(); renderTabs(); renderTable(); });
    si.addEventListener('keydown', e => { if (e.key === 'Escape') { si.value = ''; mutate(() => { S.search = ''; }); } });
    $('searchClear').onclick = () => { si.value = ''; mutate(() => { S.search = ''; }); };

    $('chipRow').addEventListener('click', e => {
      if (e.target.id === 'clearAll') { si.value = ''; mutate(() => { S.chips = []; S.sets = { conv: [], ta: [], gex: [] }; S.numeric = {}; S.search = ''; S.favsOnly = false; }); return; }
      if (e.target.id === 'filtersToggle') { $('chipRow').classList.toggle('collapsed'); return; }
      if (e.target.id === 'favsOnlyChip') { mutate(() => { S.favsOnly = !S.favsOnly; }); return; }
      const sb = e.target.closest('[data-set]'); if (sb) { openSetMenu(sb.dataset.set, sb.getBoundingClientRect()); return; }
      const b = e.target.closest('[data-chip]'); if (!b) return;
      const id = b.dataset.chip;
      mutate(() => { const i = S.chips.indexOf(id); if (i >= 0) S.chips.splice(i, 1); else S.chips.push(id); });
    });

    $('tableHost').addEventListener('click', e => {
      const fav = e.target.closest('[data-fav]');
      if (fav) { e.stopPropagation(); V.toggleFav(fav.dataset.fav); updateFavCount(); renderTable(); return; }
      if (e.target.closest('[data-tv]')) { e.stopPropagation(); return; }
      const fn = e.target.closest('[data-funnel]');
      if (fn) { e.stopPropagation(); openNumeric(fn.dataset.funnel, fn.getBoundingClientRect()); return; }
      const th = e.target.closest('[data-sort]');
      if (th) { clickSort(th.dataset.sort, e.shiftKey); return; }
      const tr = e.target.closest('[data-tk]');
      if (tr) selectRow(tr.dataset.tk);
    });

    $('viewBtn').onclick = e => openViewMenu(e.currentTarget.getBoundingClientRect());
    $('favsBtn').onclick = () => mutate(() => { S.favsOnly = !S.favsOnly; });
    $('colsBtn').onclick = e => openCols(e.currentTarget.getBoundingClientRect());
    $('saveBtn').onclick = saveViewModal;
    $('popScrim').onclick = closePop;

    document.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z' && document.activeElement !== si) {
        e.preventDefault(); undo();
      }
    });

    EV_SCAN.mount({
      button: $('scanBtn'), bar: $('scanBar'), text: $('scanText'), fill: $('scanFill'),
      download: $('dlCheck'), onComplete: reload, onProgress: liveReload,
    });
  }

  async function init() {
    const ui = V.loadUI();
    if (ui) Object.assign(S, ui);
    if (!S.sets) S.sets = { conv: [], ta: [], gex: [] };
    V.seedDefaults();
    wire();
    $('searchInput').value = S.search || '';
    const vname = new URLSearchParams(location.search).get('view');
    renderAll();
    await reload();
    if (vname) { const v = V.getView(vname); if (v) applyView(v); }
  }

  return { init, reload };
})();
