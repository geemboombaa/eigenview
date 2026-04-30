(() => {
  const CSS_ID = 'ev-market-context-css';
  const CSS = `
.ctx-strip{display:grid;grid-template-columns:repeat(5,1fr);gap:1px;background:var(--border);border:1px solid var(--border);border-radius:6px;overflow:visible;}
.ctx-cell{background:var(--panel);padding:10px 14px;position:relative;cursor:help;transition:background 0.1s;}
.ctx-cell:hover{background:var(--panel-2);}
.ctx-cell-label{color:var(--text-faint);font-size:9px;letter-spacing:1px;text-transform:uppercase;margin-bottom:4px;display:flex;align-items:center;gap:4px;}
.ctx-cell-value{font-size:13px;font-weight:500;line-height:1.3;}
.ctx-cell-sub{font-size:11px;color:var(--text-dim);margin-top:2px;}
.ctx-tip{position:absolute;top:calc(100% + 4px);left:0;width:280px;background:var(--panel-2);border:1px solid var(--border);border-radius:6px;padding:12px 14px;box-shadow:var(--shadow);z-index:300;display:none;font-family:var(--font-prose,-apple-system,sans-serif);}
.ctx-tip.visible{display:block;}
.tip-label{font-size:9px;letter-spacing:1.2px;color:var(--text-faint);text-transform:uppercase;margin-bottom:4px;}
.tip-def{font-size:12px;color:var(--text);margin-bottom:6px;line-height:1.5;}
.tip-now{font-size:12px;color:var(--text-dim);margin-bottom:6px;line-height:1.5;}
.tip-so{font-size:12px;color:var(--accent);line-height:1.5;}
.tip-so::before{content:"→ ";}
.regime-pill{display:inline-block;font-size:9px;letter-spacing:1.5px;text-transform:uppercase;padding:2px 7px;border-radius:3px;font-weight:600;}
.regime-green{color:var(--long,#5ee3a1);background:rgba(94,227,161,0.12);border:1px solid rgba(94,227,161,0.25);}
.regime-yellow{color:var(--warn,#ffc857);background:rgba(255,200,87,0.10);border:1px solid rgba(255,200,87,0.25);}
.regime-red{color:var(--short,#ff6b6b);background:rgba(255,107,107,0.10);border:1px solid rgba(255,107,107,0.25);}
.ctx-no-data{padding:10px 14px;font-size:11px;color:var(--warn,#ffc857);background:rgba(255,200,87,0.08);border-radius:6px;border:1px solid rgba(255,200,87,0.2);}
.ctx-skeleton{animation:ctx-pulse 1.4s ease infinite;}
@keyframes ctx-pulse{0%,100%{opacity:0.4;}50%{opacity:0.8;}}
`;

  function injectCSS() {
    if (document.getElementById(CSS_ID)) return;
    const s = document.createElement('style');
    s.id = CSS_ID;
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function fmtGex(val) {
    if (val == null) return '—';
    const b = val / 1e9;
    const sign = b >= 0 ? '+' : '';
    return `${sign}$${Math.abs(b).toFixed(1)}B`;
  }

  function gexColor(val) {
    if (val == null) return '';
    return val >= 0 ? 'color:var(--long)' : 'color:var(--short)';
  }

  function vixColor(val) {
    if (val == null) return '';
    if (val < 18) return 'color:var(--long)';
    if (val < 28) return 'color:var(--warn)';
    return 'color:var(--short)';
  }

  function dixColor(val) {
    return val != null && val > 0.43 ? 'color:var(--long)' : 'color:var(--text-dim)';
  }

  function regimePillHtml(regime) {
    if (!regime) return '<span class="regime-pill regime-yellow">UNKNOWN</span>';
    const cls = { GREEN: 'regime-green', YELLOW: 'regime-yellow', RED: 'regime-red' }[regime] || 'regime-yellow';
    return `<span class="regime-pill ${cls}">${regime}</span>`;
  }

  function cellHtml({ label, valueHtml, subHtml, tipLabel, tipDef, tipNow, tipSo }) {
    return `
      <div class="ctx-cell">
        <div class="ctx-cell-label">${label} <span style="display:inline-flex;align-items:center;justify-content:center;width:12px;height:12px;border-radius:50%;background:var(--chip-bg);border:1px solid var(--chip-border);font-size:8px;color:var(--text-faint);">?</span></div>
        <div class="ctx-cell-value">${valueHtml}</div>
        ${subHtml ? `<div class="ctx-cell-sub">${subHtml}</div>` : ''}
        <div class="ctx-tip">
          <div class="tip-label">${tipLabel}</div>
          <div class="tip-def">${tipDef}</div>
          ${tipNow ? `<div class="tip-now">${tipNow}</div>` : ''}
          ${tipSo ? `<div class="tip-so">${tipSo}</div>` : ''}
        </div>
      </div>`;
  }

  function stripHtml(r) {
    if (!r) {
      return `<div class="ctx-no-data">No macro data — run <code>eigenview fetch-macro</code> to populate.</div>`;
    }
    const contango = r.vix_contango_pct != null && r.vix_contango_pct > 0;
    const trendLabel = r.vix_contango_pct != null
      ? `${contango ? '+' : ''}${r.vix_contango_pct.toFixed(1)}%`
      : '—';

    const cells = [
      {
        label: 'MACRO REGIME',
        valueHtml: `${regimePillHtml(r.regime)} <span style="color:var(--text-dim);font-size:11px;">${r.score != null ? r.score + '/10' : ''}</span>`,
        subHtml: null,
        tipLabel: 'Macro Regime Gate',
        tipDef: 'Gate 0: scores 4 macro signals (SPX GEX, VIX term structure, DIX, breadth) 0–10. ≥7 = GREEN → screener runs normally. 4–6 = YELLOW → picks flagged. ≤3 = RED → no long picks.',
        tipNow: r.narrative || null,
        tipSo: r.regime === 'GREEN' ? 'Macro conditions favor long picks today.' : r.regime === 'RED' ? 'Macro gate blocking long picks. Short setups only.' : 'Proceed with caution — mixed macro signals.',
      },
      {
        label: 'SPX GEX',
        valueHtml: `<span style="${gexColor(r.gex_index)}">${fmtGex(r.gex_index)}</span>`,
        subHtml: r.gex_index != null ? (r.gex_index >= 0 ? 'long γ' : 'short γ') : null,
        tipLabel: 'SPX Gamma Exposure',
        tipDef: 'Net dealer gamma on SPX options. Positive = dealers long gamma, which suppresses index volatility. Negative = short gamma, which amplifies moves.',
        tipNow: r.gex_index != null ? `${fmtGex(r.gex_index)} — dealers ${r.gex_index >= 0 ? 'long gamma: market-maker hedging dampens SPX moves' : 'short gamma: hedging flows amplify index moves'}.` : null,
        tipSo: r.gex_index != null && r.gex_index < 0 ? 'Short gamma environment — favorable for options trades on individual names.' : 'Long gamma — SPX range-bound tendency. Individual names can still move sharply.',
      },
      {
        label: 'VIX TERM',
        valueHtml: r.vix_contango_pct != null
          ? `<span style="${contango ? 'color:var(--long)' : 'color:var(--short)'}">${contango ? 'Contango' : 'Backwardation'}</span>`
          : '<span style="color:var(--text-dim)">—</span>',
        subHtml: r.vix_contango_pct != null ? trendLabel : null,
        tipLabel: 'VIX Term Structure',
        tipDef: 'Spread between VIX M2 (second month) and M1 (front month). Contango (M2 > M1) = calm, normal market. Backwardation (M2 < M1) = front-month fear premium.',
        tipNow: r.vix_m1 != null && r.vix_m2 != null ? `M1 = ${r.vix_m1.toFixed(1)}, M2 = ${r.vix_m2.toFixed(1)}. ${contango ? 'Contango' : 'Backwardation'} ${trendLabel}.` : null,
        tipSo: contango ? 'No near-term fear. Favorable for buying vol on catalyst plays.' : 'Elevated front-month fear. Options expensive — favor spreads over naked buys.',
      },
      {
        label: 'DIX',
        valueHtml: r.dix != null
          ? `<span style="${dixColor(r.dix)}">${(r.dix * 100).toFixed(1)}%</span>`
          : '<span style="color:var(--text-dim)">—</span>',
        subHtml: r.dix != null ? (r.dix > 0.43 ? '▲ bullish' : '▼ neutral') : null,
        tipLabel: 'Dark Pool Index (DIX)',
        tipDef: 'SqueezeMetrics measure of dark pool buying as % of total SPX volume. >43% = institutional buying pressure.',
        tipNow: r.dix != null ? `${(r.dix * 100).toFixed(1)}% — ${r.dix > 0.43 ? 'above the 43% bullish threshold' : 'below bullish threshold'}.` : null,
        tipSo: r.dix != null && r.dix > 0.43 ? 'Dark pool buyers active. Historically bullish for equities 1–2 week horizon.' : 'Dark pool buying subdued. Institutional conviction lower.',
      },
      {
        label: 'VIX',
        valueHtml: r.vix_m1 != null
          ? `<span style="${vixColor(r.vix_m1)}">${r.vix_m1.toFixed(1)}</span>`
          : '<span style="color:var(--text-dim)">—</span>',
        subHtml: r.vix_m1 != null ? (r.vix_m1 < 18 ? 'low vol' : r.vix_m1 < 28 ? 'elevated' : 'fear') : null,
        tipLabel: 'CBOE VIX (Spot)',
        tipDef: '30-day implied volatility of SPX options. Below 18 = low vol regime. 18–28 = elevated. Above 28 = fear.',
        tipNow: r.vix_m1 != null ? `VIX ${r.vix_m1.toFixed(1)} — ${r.vix_m1 < 18 ? 'low volatility regime' : r.vix_m1 < 28 ? 'elevated volatility' : 'fear regime'}.` : null,
        tipSo: r.vix_m1 != null && r.vix_m1 < 18 ? 'Options relatively cheap on index level. Favorable for buying options on catalyst names.' : 'Options more expensive. Prefer spreads to cap cost.',
      },
    ];

    return `<div class="ctx-strip">${cells.map(cellHtml).join('')}</div>`;
  }

  function bindTooltips(container) {
    container.querySelectorAll('.ctx-cell').forEach(cell => {
      const tip = cell.querySelector('.ctx-tip');
      if (!tip) return;
      cell.addEventListener('mouseenter', () => tip.classList.add('visible'));
      cell.addEventListener('mouseleave', () => tip.classList.remove('visible'));
    });
  }

  class MarketContextModule extends (window.EV ? window.EV.Module : class { constructor(el,cfg){this.el=el;this.config=cfg;this._unsubs=[];} mount(){} unmount(){this._unsubs.forEach(f=>f());this._unsubs=[];} _sub(k,f){if(window.EV)this._unsubs.push(window.EV.Store.subscribe(k,f));} }) {
    mount() {
      injectCSS();
      this.el.innerHTML = '<div class="ctx-skeleton" style="height:52px;background:var(--panel);border-radius:6px;border:1px solid var(--border);"></div>';

      const render = (regime) => {
        this.el.innerHTML = stripHtml(regime);
        bindTooltips(this.el);
      };

      const current = window.EV && window.EV.Store.get('regime');
      if (current) render(current);

      this._sub('regime', render);
    }

    resize(size) {
      // M and L both show the same strip; L could show extra detail in future
    }
  }

  MarketContextModule.id = 'market-context';
  MarketContextModule.label = 'Market Context';
  MarketContextModule.defaultSize = 'M';
  MarketContextModule.supportedSizes = ['M', 'L'];

  if (window.EV && window.EV.registry) {
    window.EV.registry.register(MarketContextModule);
  }
  window.MarketContextModule = MarketContextModule;
})();
