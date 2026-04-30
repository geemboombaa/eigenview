(() => {
  const Base = window.EV?.Module ?? class {
    constructor(el, config) { this.el = el; this.config = config || {}; this._subs = []; }
    mount() {}
    unmount() { this._subs.forEach(u => u()); this._subs = []; }
    resize() {}
    _sub(key, fn) {
      if (window.EV?.Store) { this._subs.push(window.EV.Store.subscribe(key, fn)); }
    }
    _html(h) { this.el.innerHTML = h; }
    _qs(sel) { return this.el.querySelector(sel); }
    _qsa(sel) { return this.el.querySelectorAll(sel); }
  };

  const FACTORS = [
    { key: 'macro_regime', label: 'MACRO' },
    { key: 'technical',    label: 'TECH' },
    { key: 'gex',          label: 'GEX' },
    { key: 'flow',         label: 'FLOW' },
    { key: 'dormant',      label: 'DORMANT' },
    { key: 'sentiment',    label: 'SENTIMENT' },
  ];

  const STYLE = `
<style id="ev-factor-strip-style">
.factor-strip { display:flex; gap:8px; padding:8px; flex-wrap:wrap; height:100%; box-sizing:border-box; align-items:center; }
.factor-strip.grid-sm { display:grid; grid-template-columns:repeat(3,1fr); }
.factor-cell {
  flex:1; min-width:80px; padding:8px 10px; border-radius:8px;
  background:var(--bg-secondary,#1e1e2e); border:1px solid var(--border,#2a2a3e);
  cursor:pointer; transition:border-color 0.2s, box-shadow 0.2s;
  display:flex; flex-direction:column; gap:4px;
}
.factor-cell:hover { border-color:var(--accent,#7c6af5); }
.factor-cell.firing { border-color:var(--success,#22c55e); box-shadow:0 0 8px color-mix(in srgb, var(--success,#22c55e) 30%, transparent); animation:fsPulse 1s ease-in-out; }
@keyframes fsPulse { 0%,100%{box-shadow:0 0 8px color-mix(in srgb,var(--success,#22c55e) 30%,transparent)} 50%{box-shadow:0 0 16px color-mix(in srgb,var(--success,#22c55e) 60%,transparent)} }
.factor-cell-top { display:flex; align-items:center; justify-content:space-between; }
.factor-label { font-size:10px; font-weight:700; letter-spacing:0.08em; color:var(--text-muted,#888); }
.factor-pill {
  font-size:9px; font-weight:700; padding:2px 6px; border-radius:20px; letter-spacing:0.05em;
}
.factor-pill.fire { background:color-mix(in srgb,var(--success,#22c55e) 20%,transparent); color:var(--success,#22c55e); }
.factor-pill.off  { background:color-mix(in srgb,var(--text-muted,#888) 15%,transparent); color:var(--text-muted,#888); }
.factor-bar-track { height:3px; background:var(--border,#2a2a3e); border-radius:2px; overflow:hidden; }
.factor-bar-fill  { height:100%; border-radius:2px; transition:width 0.4s; }
.factor-bar-fill.fire { background:var(--success,#22c55e); }
.factor-bar-fill.off  { background:var(--text-muted,#888); }
.factor-lbl-text  { font-size:10px; color:var(--text-muted,#888); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.factor-strip-empty { width:100%; text-align:center; color:var(--text-muted,#888); font-size:13px; padding:16px; }
</style>`;

  class FactorStripModule extends Base {
    static id = 'factor-strip';

    mount() {
      if (!document.getElementById('ev-factor-strip-style')) {
        document.head.insertAdjacentHTML('beforeend', STYLE);
      }
      this._render(null);
      this._sub('selectedPick', pick => this._render(pick));
    }

    _render(pick) {
      const isSmall = this.el.offsetWidth < 400;
      if (!pick || !pick.factors) {
        this._html(`<div class="factor-strip${isSmall ? ' grid-sm' : ''}"><span class="factor-strip-empty">Select a pick to view factors</span></div>`);
        return;
      }
      const ticker = pick.ticker || '';
      const cells = FACTORS.map(({ key, label }) => {
        const f = pick.factors[key] || {};
        const firing = !!f.firing;
        const strength = typeof f.strength === 'number' ? f.strength : 0;
        const lbl = f.label || '—';
        const pct = Math.round(strength * 100);
        return `
<div class="factor-cell${firing ? ' firing' : ''}" data-factor="${key}" data-ticker="${ticker}" data-label="${lbl}">
  <div class="factor-cell-top">
    <span class="factor-label">${label}</span>
    <span class="factor-pill ${firing ? 'fire' : 'off'}">${firing ? 'FIRE' : 'OFF'}</span>
  </div>
  <div class="factor-bar-track"><div class="factor-bar-fill ${firing ? 'fire' : 'off'}" style="width:${pct}%"></div></div>
  <div class="factor-lbl-text">${lbl}</div>
</div>`;
      }).join('');
      this._html(`<div class="factor-strip${isSmall ? ' grid-sm' : ''}">${cells}</div>`);
      this._qsa('.factor-cell').forEach(cell => {
        cell.addEventListener('click', () => {
          const fKey = cell.dataset.factor;
          const t = cell.dataset.ticker;
          const l = cell.dataset.label;
          const name = FACTORS.find(f => f.key === fKey)?.label || fKey;
          if (window.EV?.Store) {
            EV.Store.set('chatPrefill', `Explain the ${name} factor for ${t}: ${l}`);
          }
        });
      });
    }

    resize(size) {
      this._render(window.EV?.Store?.get('selectedPick') ?? null);
    }
  }

  if (window.EV?.registry) {
    EV.registry.register(FactorStripModule);
  } else {
    window.__EV_PENDING_MODULES = window.__EV_PENDING_MODULES || [];
    window.__EV_PENDING_MODULES.push(FactorStripModule);
  }
})();
