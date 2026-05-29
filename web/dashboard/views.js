/* EigenView dashboard — favorites + saved views + UI-state persistence.
   Pure localStorage CRUD. No rendering here. */

window.EV_VIEWS = (() => {
  const K_FAVS = 'ev:favs';
  const K_VIEWS = 'ev:views';
  const K_UI = 'ev:ui';

  function read(key, fallback) {
    try { const v = JSON.parse(localStorage.getItem(key)); return v == null ? fallback : v; }
    catch { return fallback; }
  }
  function write(key, val) { localStorage.setItem(key, JSON.stringify(val)); }

  // --- favorites ---
  function getFavs() { return read(K_FAVS, []); }
  function isFav(t) { return getFavs().includes(t); }
  function toggleFav(t) {
    const f = getFavs();
    const i = f.indexOf(t);
    if (i >= 0) f.splice(i, 1); else f.push(t);
    write(K_FAVS, f);
    return f;
  }

  // --- saved views ---
  function getViews() { return read(K_VIEWS, []); }
  function getView(name) { return getViews().find(v => v.name === name) || null; }
  function saveView(view) {
    const all = getViews().filter(v => v.name !== view.name);
    all.push(view);
    write(K_VIEWS, all);
    return all;
  }
  function deleteView(name) {
    const all = getViews().filter(v => v.name !== name);
    write(K_VIEWS, all);
    return all;
  }

  // 4 pre-built defaults — seeded once if a view of that name doesn't exist.
  const DEFAULTS = [
    { name: 'Morning Alpha', mode: 'daily', search: '', chips: ['fresh'], sets: { conv: [4, 5], ta: [], gex: [] }, numeric: {}, cols: null, sort: [{ key: 'conv', dir: 'desc' }], favsOnly: false, builtin: true },
    { name: 'Dormant Watch', mode: 'all',   search: '', chips: ['dorm'],  sets: { conv: [], ta: [], gex: [] }, numeric: {}, cols: null, sort: [{ key: 'dorm', dir: 'desc' }], favsOnly: false, builtin: true },
    { name: 'Flow Surge',    mode: 'all',   search: '', chips: ['flow'],  sets: { conv: [], ta: [], gex: [] }, numeric: {}, cols: null, sort: [{ key: 'flow', dir: 'desc' }], favsOnly: false, builtin: true },
    { name: 'High TA Longs', mode: 'all',   search: '', chips: ['long'],  sets: { conv: [], ta: ['HIGH'], gex: [] }, numeric: {}, cols: null, sort: [{ key: 'ta', dir: 'desc' }], favsOnly: false, builtin: true },
  ];
  function seedDefaults() {
    const existing = new Set(getViews().map(v => v.name));
    let all = getViews();
    DEFAULTS.forEach(d => { if (!existing.has(d.name)) all.push({ ...d }); });
    write(K_VIEWS, all);
    return all;
  }

  // --- last UI state (restore on refresh) ---
  function loadUI() { return read(K_UI, null); }
  function saveUI(ui) { write(K_UI, ui); }

  return {
    getFavs, isFav, toggleFav,
    getViews, getView, saveView, deleteView, seedDefaults, DEFAULTS,
    loadUI, saveUI,
  };
})();
