/* EigenEdge dashboard — data loader.
   Served same-origin by FastAPI → relative URLs. Real endpoints only.
   NO caps, NO fallback to old dates, NO invented thresholds. */

window.EV_DATA = (() => {
  const BASE = '';   // same-origin

  async function fetchJSON(path) {
    const res = await fetch(BASE + path, { cache: 'no-store' });
    if (!res.ok) throw new Error(`${path} → ${res.status}`);
    return res.json();
  }

  // GEX dealer-gamma regime → trader-facing meaning.
  function gexRegime(label) {
    const s = (label || '').toLowerCase();
    if (s.includes('flip')) return { key: 'flip', label: 'Flip Pivot', cls: 'flip' };
    if (s.includes('short')) return { key: 'run', label: 'Price Run', cls: 'run' };
    if (s.includes('long')) return { key: 'pin', label: 'Price Pin', cls: 'pin' };
    return { key: '', label: '—', cls: 'none' };
  }

  // Raw setup label → friendly 1-2 word name.
  const SETUP_MAP = {
    pullback: 'Pullback', pullback_structure: 'Pullback Support',
    breakout: 'Breakout', breakdown: 'Breakdown',
    bb_mr_long: 'Oversold Bounce', bb_mr_short: 'Overbought Fade',
    rally_short: 'Bear Rally',
    reversal_long: 'Bottom Reversal', reversal_short: 'Top Reversal',
    ema_reclaim: 'EMA Reclaim', ema_rejection: 'EMA Reject',
    failed_breakout: 'Failed Breakout', failed_breakdown: 'Failed Breakdown',
    ema200_snap_long: '200 Snapback', ema200_snap_short: '200 Fade',
    flag: 'Flag', dormant_activation: 'Dormant Wake', flow_driven: 'Flow Driven',
    no_pattern: '—', '': '—',
  };
  function setupName(raw) { return SETUP_MAP[raw] || raw; }

  // TA probability tier → short display.
  function taTier(raw) {
    const s = (raw || '').toUpperCase();
    if (s === 'HIGH') return 'HIGH';
    if (s.startsWith('SPEC')) return 'SPEC';
    return '';
  }

  function num(v) { return (typeof v === 'number' && isFinite(v)) ? v : null; }

  function normPick(p, src) {
    const f = p.factors || {};
    const ta = f.technical || {}, gex = f.gex || {}, fl = f.flow || {},
          dm = f.dormant || {}, st = f.sentiment || {};
    const g = gex.detail || {};
    const tier = taTier(p.ta_tier || (ta.detail || {}).probability_tier);
    const reg = gexRegime(gex.label || g.regime);
    return {
      ticker: p.ticker,
      date: p.date || null,
      dir: (p.direction || 'long').toLowerCase(),
      setupRaw: p.setup_type || '',
      setup: setupName(p.setup_type || ''),
      conv: p.conviction || 0,
      price: num(p.spot),
      entryLow: num(p.entry_low), entryHigh: num(p.entry_high),
      stop: num(p.stop), target: num(p.target),
      thesis: p.thesis || '',
      fresh: (p.freshness || '').toLowerCase() === 'fresh',
      taTier: tier,
      callWall: num(g.call_wall), putWall: num(g.put_wall),
      gammaFlip: num(g.gamma_flip),
      gexKey: reg.key, gexLabel: reg.label, gexCls: reg.cls,
      fStr: {
        flow: fl.strength || 0, dorm: dm.strength || 0, sent: st.strength || 0,
        ta: ta.strength || 0, gex: gex.strength || 0,
      },
      inPicks: true,
      exchange: p.exchange || null,
      src,
    };
  }

  const SHORT_RE = /short|bear|rejection|breakdown|reversal_short|failed_breakout|fade/i;

  function normMatrix(r) {
    const reg = gexRegime(r.gex_label);
    return {
      ticker: r.ticker,
      date: r.date || null,
      dir: SHORT_RE.test(r.setup_type || '') ? 'short' : 'long',
      setupRaw: r.setup_type || '',
      setup: setupName(r.setup_type || ''),
      conv: r.conviction || 0,
      price: num(r.spot),
      entryLow: null, entryHigh: null, stop: null, target: null,
      thesis: '',
      fresh: false,
      taTier: taTier(r.ta_tier),
      callWall: null, putWall: null, gammaFlip: null,
      gexKey: reg.key, gexLabel: reg.label, gexCls: reg.cls,
      fStr: {
        flow: r.flow_str || 0, dorm: r.dormant_str || 0, sent: r.sentiment_str || 0,
        ta: r.ta_str || 0, gex: r.gex_str || 0,
      },
      inPicks: !!r.in_picks,
      exchange: null,
      src: 'all',
    };
  }

  async function loadAll() {
    const state = { daily: [], week: [], all: [], regime: null, todaySet: new Set(), errors: [] };

    const [today, week, regime, matrix] = await Promise.all([
      fetchJSON('/api/picks').catch(e => { state.errors.push(`picks: ${e.message}`); return []; }),
      fetchJSON('/api/picks/week').catch(e => { state.errors.push(`week: ${e.message}`); return []; }),
      fetchJSON('/api/market/regime').catch(e => { state.errors.push(`regime: ${e.message}`); return null; }),
      fetchJSON('/api/signals/matrix').catch(e => { state.errors.push(`matrix: ${e.message}`); return { rows: [] }; }),
    ]);

    state.regime = regime;
    state.daily = today.map(p => normPick(p, 'daily'));
    state.todaySet = new Set(state.daily.map(r => r.ticker));

    // WEEKLY — "today wins": drop tickers in today's daily, then one row per ticker
    // (week endpoint is already date desc → first seen = most recent).
    const seen = new Set();
    state.week = week
      .map(p => normPick(p, 'week'))
      .filter(r => !state.todaySet.has(r.ticker))
      .filter(r => { if (seen.has(r.ticker)) return false; seen.add(r.ticker); return true; });

    // ALL — exactly what the matrix returns (server gates TA OR dormant). No client filter.
    state.all = (matrix.rows || []).map(normMatrix);
    return state;
  }

  function tvLink(row) {
    const ex = (row && row.exchange) || 'NASDAQ';
    const tk = typeof row === 'string' ? row : row.ticker;
    return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(ex)}%3A${encodeURIComponent(tk)}`;
  }

  async function triggerScan(refresh) {
    // refresh=true → backend pulls fresh macro + news + prices + chains before the pipeline.
    const q = refresh ? '?download=true' : '?download=false';
    const res = await fetch(BASE + '/api/scan' + q, { method: 'POST' });
    return res.json();
  }
  function scanStatus() { return fetchJSON('/api/scan/status'); }

  return { loadAll, tvLink, triggerScan, scanStatus, gexRegime, setupName, taTier };
})();
