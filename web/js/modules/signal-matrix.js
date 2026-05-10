(() => {
  const CSS_ID = 'ev-signal-matrix-css';
  const CSS = `
.sm-matrix{display:flex;flex-direction:column;height:100%;overflow:hidden;}
.sm-head{display:flex;align-items:center;padding:12px 16px 8px;border-bottom:1px solid var(--border);flex-shrink:0;gap:10px;}
.sm-title{font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--text-faint);font-weight:600;flex:1;}
.sm-count{font-size:10px;color:var(--text-dim);}
.sm-table-wrap{flex:1;overflow-y:auto;overflow-x:auto;}
.sm-table{width:100%;border-collapse:collapse;font-size:11px;}
.sm-table th{position:sticky;top:0;background:var(--panel);padding:6px 10px;text-align:left;font-size:9px;letter-spacing:1.2px;text-transform:uppercase;color:var(--text-faint);border-bottom:1px solid var(--border);white-space:nowrap;font-weight:600;}
.sm-table th.sm-center{text-align:center;}
.sm-table td{padding:7px 10px;border-bottom:1px solid var(--border-soft,#151a22);vertical-align:middle;white-space:nowrap;}
.sm-row{cursor:pointer;transition:background 0.1s;}
.sm-row:hover{background:var(--panel-3);}
.sm-row.selected{background:rgba(94,227,161,0.06);}
.sm-ticker{font-size:13px;font-weight:600;letter-spacing:0.3px;}
.sm-dir{text-align:center;}
.sm-dir-tag{font-size:8px;padding:1px 5px;border-radius:2px;letter-spacing:0.8px;font-weight:600;}
.sm-dir-long{color:var(--long,#5ee3a1);background:rgba(94,227,161,.1);border:1px solid rgba(94,227,161,.25);}
.sm-dir-short{color:var(--short,#ff6b6b);background:rgba(255,107,107,.08);border:1px solid rgba(255,107,107,.25);}
.sm-setup{color:var(--text-dim);max-width:140px;overflow:hidden;text-overflow:ellipsis;}
.sm-factor{text-align:center;}
.sm-dot{display:inline-block;width:8px;height:8px;border-radius:50%;}
.sm-dot-on{background:var(--accent,#5ee3a1);}
.sm-dot-off{background:var(--border,#232836);}
.sm-stars{display:flex;gap:2px;align-items:center;justify-content:center;}
.sm-star{font-size:10px;color:var(--border);line-height:1;}
.sm-star.on{color:var(--accent,#5ee3a1);}
.sm-empty{padding:40px 20px;text-align:center;color:var(--text-faint);font-size:12px;}
`;

  const FACTORS = [
    { key: 'technical', label: 'TA' },
    { key: 'gex',       label: 'GEX' },
    { key: 'flow',      label: 'FLOW' },
    { key: 'dormant',   label: 'DORM' },
    { key: 'sentiment', label: 'SENT' },
  ];

  const PATTERN_ABBR = {
    breakout: 'Breakout',
    pullback_in_trend: 'Pullback',
    compression_break: 'Comp. Break',
    ema_reclaim: 'EMA Reclaim',
    base_breakout: 'Base BO',
    oversold_bounce: 'OS Bounce',
    failed_breakdown: 'Failed BD',
    bullish_reversal: 'Bull Rev',
    bearish_reversal: 'Bear Rev',
    breakdown: 'Breakdown',
    rally_in_downtrend: 'Rally Short',
    compression_break_down: 'Comp. BD',
    ema_rejection: 'EMA Reject',
    base_breakdown: 'Base BD',
    overbought_reversal: 'OB Rev',
    failed_breakout: 'Failed BO',
  };

  function starsHtml(conviction) {
    const n = Math.max(0, Math.min(5, conviction || 0));
    return Array.from({ length: 5 }, (_, i) =>
      `<span class="sm-star${i < n ? ' on' : ''}">★</span>`
    ).join('');
  }

  function factorDot(pick, factorKey) {
    const f = pick.factors?.[factorKey];
    const on = f?.firing === true;
    return `<td class="sm-factor"><span class="sm-dot ${on ? 'sm-dot-on' : 'sm-dot-off'}" title="${factorKey}: ${on ? 'firing' : 'not firing'}"></span></td>`;
  }

  function rowHtml(pick, selected) {
    const dir = (pick.direction || 'long').toLowerCase();
    const setup = PATTERN_ABBR[pick.setup_type] || (pick.setup_type || '').replace(/_/g, ' ');
    const dirTag = `<span class="sm-dir-tag sm-dir-${dir}">${dir.toUpperCase()}</span>`;

    return `
<tr class="sm-row${selected ? ' selected' : ''}" data-ticker="${pick.ticker}">
  <td><span class="sm-ticker">${pick.ticker}</span></td>
  <td class="sm-dir">${dirTag}</td>
  <td class="sm-setup">${setup}</td>
  ${FACTORS.map(f => factorDot(pick, f.key)).join('')}
  <td><div class="sm-stars">${starsHtml(pick.conviction)}</div></td>
</tr>`;
  }

  function tableHtml(picks, selectedTicker) {
    if (!picks || !picks.length) {
      return `<div class="sm-empty">No picks to display.<br>Run a scan to populate the matrix.</div>`;
    }
    const headers = ['TICKER', 'DIR', 'SETUP', ...FACTORS.map(f => f.label), '★★★★★'];
    const thead = `<thead><tr>${headers.map((h, i) =>
      `<th${i > 2 ? ' class="sm-center"' : ''}>${h}</th>`
    ).join('')}</tr></thead>`;
    const tbody = `<tbody>${picks.map(p => rowHtml(p, p.ticker === selectedTicker)).join('')}</tbody>`;
    return `<table class="sm-table">${thead}${tbody}</table>`;
  }

  const EV_SignalMatrix = {
    _el: null,
    _unsubs: [],

    mount(el) {
      this._el = el;
      this._injectCSS();
      el.innerHTML = '';
      const wrap = document.createElement('div');
      wrap.className = 'sm-matrix';
      wrap.innerHTML = `
        <div class="sm-head">
          <span class="sm-title">Signal Matrix</span>
          <span class="sm-count" id="sm-count"></span>
        </div>
        <div class="sm-table-wrap" id="sm-table-wrap"></div>`;
      el.appendChild(wrap);

      this._render();

      // subscribe to picks and selectedTicker changes
      if (window.EV) {
        this._unsubs.push(window.EV.Store.subscribe('picks', () => this._render()));
        this._unsubs.push(window.EV.Store.subscribe('selectedTicker', () => this._render()));
      }

      // row click → select pick
      wrap.addEventListener('click', e => {
        const row = e.target.closest('[data-ticker]');
        if (!row) return;
        const ticker = row.dataset.ticker;
        const picks = window.EV?.Store.get('picks') || [];
        const pick = picks.find(p => p.ticker === ticker);
        window.EV?.Store.set('selectedTicker', ticker);
        window.EV?.Store.set('selectedPick', pick || { ticker });
      });
    },

    load() {
      this._render();
    },

    _render() {
      if (!this._el) return;
      const tableWrap = this._el.querySelector('#sm-table-wrap');
      const countEl = this._el.querySelector('#sm-count');
      const picks = window.EV?.Store.get('picks') || [];
      const selectedTicker = window.EV?.Store.get('selectedTicker');
      if (tableWrap) tableWrap.innerHTML = tableHtml(picks, selectedTicker);
      if (countEl) countEl.textContent = picks.length ? `${picks.length} signal${picks.length !== 1 ? 's' : ''}` : '';
    },

    _injectCSS() {
      if (document.getElementById(CSS_ID)) return;
      const s = document.createElement('style');
      s.id = CSS_ID;
      s.textContent = CSS;
      document.head.appendChild(s);
    },

    unmount() {
      this._unsubs.forEach(f => f());
      this._unsubs = [];
      if (this._el) this._el.innerHTML = '';
      this._el = null;
    }
  };

  window.EV_SignalMatrix = EV_SignalMatrix;
})();
