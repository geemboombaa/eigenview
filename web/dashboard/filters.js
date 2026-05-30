/* EigenEdge dashboard — column registry, chips, multi-select sets, predicates.
   Operates on the normalized row schema from data.js. */

window.EV_FILTERS = (() => {

  // key, label, align, kind, get(row), searchable, numeric, defVisible, weekOnly
  const COLUMNS = [
    { key: 'ticker', label: 'Ticker',    align: 'l', kind: 'ticker', get: r => r.ticker,   searchable: true, defVisible: true },
    { key: 'dir',    label: 'Dir',       align: 'l', kind: 'dir',    get: r => r.dir,      searchable: true, defVisible: true },
    { key: 'conv',   label: 'Conv',      align: 'c', kind: 'conv',   get: r => r.conv || 0, defVisible: true },
    { key: 'ta',     label: 'TA',        align: 'c', kind: 'tatier', get: r => r.taTier,   searchable: true, defVisible: true },
    { key: 'gex',    label: 'GEX',       align: 'c', kind: 'gexpill',get: r => r.gexLabel, searchable: true, defVisible: true },
    { key: 'flow',   label: 'Flow',      align: 'c', kind: 'flabel', get: r => r.fStr.flow, numeric: true, defVisible: true },
    { key: 'dorm',   label: 'Dorm',      align: 'c', kind: 'flabel', get: r => r.fStr.dorm, numeric: true, defVisible: true },
    { key: 'sent',   label: 'Sentiment', align: 'c', kind: 'flabel', get: r => r.fStr.sent, numeric: true, defVisible: true },
    { key: 'fresh',  label: 'Fresh',     align: 'c', kind: 'fresh',  get: r => r.fresh,    searchable: true, defVisible: true },
    { key: 'price',  label: 'Price',     align: 'c', kind: 'price',  get: r => r.price,    numeric: true, defVisible: true },
    { key: 'entry',  label: 'Entry',     align: 'c', kind: 'entry',  get: r => r.entryLow, numeric: true, defVisible: true },
    { key: 'stop',   label: 'Stop',      align: 'c', kind: 'price',  get: r => r.stop,     numeric: true, defVisible: true },
    { key: 'target', label: 'Target',    align: 'c', kind: 'price',  get: r => r.target,   numeric: true, defVisible: true },
    { key: 'tv',     label: '↗',         align: 'c', kind: 'tv',     get: () => null, defVisible: true },
    { key: 'setup',  label: 'Setup',     align: 'l', kind: 'text',   get: r => r.setup,    searchable: true },
    { key: 'callwall', label: 'Call Wall', align: 'c', kind: 'price', get: r => r.callWall, numeric: true },
    { key: 'putwall',  label: 'Put Wall',  align: 'c', kind: 'price', get: r => r.putWall, numeric: true },
    { key: 'gflip',    label: 'γ Flip',    align: 'c', kind: 'price', get: r => r.gammaFlip, numeric: true },
    { key: 'date',   label: 'Date',      align: 'c', kind: 'text',   get: r => r.date,     searchable: true, weekOnly: true },
  ];
  const COL_BY_KEY = Object.fromEntries(COLUMNS.map(c => [c.key, c]));
  const NUMERIC_COLS = COLUMNS.filter(c => c.numeric);
  const SEARCHABLE = COLUMNS.filter(c => c.searchable);

  function defaultVisible() { return COLUMNS.filter(c => c.defVisible).map(c => c.key); }

  // Toggle chips (AND). Label has no ✓ — render adds it + colour when active.
  const CHIPS = [
    { id: 'long',  label: 'LONG',  test: r => r.dir === 'long' },
    { id: 'short', label: 'SHORT', test: r => r.dir === 'short' },
    { id: 'flow',  label: 'FLOW',  test: r => r.fStr.flow > 0 },
    { id: 'fresh', label: 'FRESH', test: r => r.fresh === true },
  ];
  const CHIP_BY_ID = Object.fromEntries(CHIPS.map(c => [c.id, c]));

  // Dormant state / sentiment direction → dropdown category keys.
  function dormCat(raw) {
    const s = (raw || '').toLowerCase();
    if (s.includes('active')) return 'active';
    if (s.includes('accumul')) return 'accum';
    if (s.includes('dormant')) return 'dormant';
    return 'none';
  }
  function sentCat(raw) {
    const s = (raw || '').toLowerCase();
    if (s.includes('bull')) return 'bull';
    if (s.includes('bear')) return 'bear';
    if (s.includes('neutral')) return 'neutral';
    return 'none';
  }

  // Multi-select sets (dropdowns). An empty set = no constraint.
  const SETS = {
    conv: { label: 'Conv', options: [1, 2, 3, 4, 5].map(v => ({ v, label: `${v}★` })), getKey: r => r.conv || 0 },
    ta:   { label: 'TA',   options: [{ v: 'HIGH', label: 'High' }, { v: 'SPEC', label: 'Speculative' }], getKey: r => r.taTier },
    gex:  { label: 'GEX',  options: [{ v: 'pin', label: 'Price Pin' }, { v: 'run', label: 'Price Run' }, { v: 'flip', label: 'Flip Pivot' }], getKey: r => r.gexKey },
    dorm: { label: 'Dormant', options: [{ v: 'active', label: 'Active' }, { v: 'accum', label: 'Accumulating' }, { v: 'dormant', label: 'Dormant' }, { v: 'none', label: 'Not in universe' }], getKey: r => dormCat(r.fLbl.dorm) },
    sent: { label: 'Sentiment', options: [{ v: 'bull', label: 'Bullish' }, { v: 'bear', label: 'Bearish' }, { v: 'neutral', label: 'Neutral' }, { v: 'none', label: 'No data' }], getKey: r => sentCat(r.fLbl.sent) },
  };

  function searchString(row) {
    const parts = SEARCHABLE.map(c => {
      const v = c.get(row);
      if (c.key === 'fresh') return v ? 'fresh' : '';
      return v ?? '';
    });
    return parts.join(' ').toLowerCase();
  }

  // state = { search, chips:[ids], sets:{conv:[],ta:[],gex:[]}, numeric:{key:{min,max}}, favsOnly, favs:Set }
  function apply(rows, state) {
    const terms = (state.search || '').trim().toLowerCase().split(/\s+/).filter(Boolean);
    const activeChips = (state.chips || []).map(id => CHIP_BY_ID[id]).filter(Boolean);
    const ranges = Object.entries(state.numeric || {});
    const sets = state.sets || {};
    const favs = state.favs;

    return rows.filter(row => {
      if (state.favsOnly && favs && !favs.has(row.ticker)) return false;
      if (terms.length) {
        const s = searchString(row);
        if (!terms.every(t => s.includes(t))) return false;
      }
      for (const c of activeChips) if (!c.test(row)) return false;
      for (const [name, def] of Object.entries(SETS)) {
        const sel = sets[name];
        if (sel && sel.length) {
          if (!sel.includes(def.getKey(row))) return false;
        }
      }
      for (const [key, rg] of ranges) {
        const col = COL_BY_KEY[key]; if (!col) continue;
        const v = col.get(row);
        if (v == null) return false;
        if (rg.min != null && v < rg.min) return false;
        if (rg.max != null && v > rg.max) return false;
      }
      return true;
    });
  }

  return { COLUMNS, COL_BY_KEY, NUMERIC_COLS, CHIPS, CHIP_BY_ID, SETS, defaultVisible, searchString, apply };
})();
