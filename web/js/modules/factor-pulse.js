(() => {
  const CSS_ID = 'ev-signal-matrix-css';
  const CSS = `
.sm-module{display:flex;flex-direction:column;height:100%;overflow:hidden;}
.sm-head{display:flex;align-items:center;justify-content:space-between;padding:10px 14px 8px;flex-shrink:0;border-bottom:1px solid var(--border-soft);}
.sm-title{font-size:12px;font-weight:600;letter-spacing:0.5px;color:var(--text);}
.sm-controls{display:flex;align-items:center;gap:8px;}
.sm-filters{display:flex;gap:3px;flex-wrap:wrap;}
.sm-filter{background:transparent;border:1px solid var(--border);color:var(--text-faint);padding:2px 7px;border-radius:3px;font-family:var(--font-mono);font-size:9px;cursor:pointer;letter-spacing:0.5px;white-space:nowrap;}
.sm-filter:hover{color:var(--text);}
.sm-filter.active{color:var(--accent);border-color:rgba(94,227,161,0.3);background:rgba(94,227,161,0.05);}
.sm-refresh{background:transparent;border:1px solid var(--border);color:var(--text-dim);padding:3px 8px;border-radius:3px;font-size:11px;cursor:pointer;flex-shrink:0;}
.sm-refresh:hover{color:var(--text);}
.sm-table-wrap{overflow:auto;flex:1;}
.sm-table{width:100%;border-collapse:collapse;font-size:11px;}
.sm-table thead{position:sticky;top:0;z-index:2;background:var(--panel);}
.sm-th{background:var(--panel-3);color:var(--text-faint);padding:5px 6px;text-align:center;font-size:9px;letter-spacing:0.8px;cursor:pointer;white-space:nowrap;user-select:none;border-bottom:1px solid var(--border);}
.sm-th:hover,.sm-th-active{color:var(--accent);}
.sm-th-ticker{text-align:left;min-width:90px;padding-left:10px;}
.sm-row{cursor:pointer;transition:background 0.08s;}
.sm-row:hover td{background:rgba(255,255,255,0.03) !important;}
.sm-row-pick td{background:rgba(94,227,161,0.025);}
.sm-row-pick:hover td{background:rgba(94,227,161,0.06) !important;}
.sm-td-ticker{padding:5px 8px 5px 10px;border-bottom:1px solid var(--border-soft);}
.sm-ticker{font-size:12px;font-weight:600;color:var(--text);display:flex;align-items:center;gap:5px;}
.sm-pick-badge{font-size:8px;padding:1px 4px;border-radius:2px;color:var(--accent);border:1px solid rgba(94,227,161,0.3);background:rgba(94,227,161,0.08);letter-spacing:0.5px;flex-shrink:0;}
.sm-setup-lbl{font-size:9px;color:var(--text-faint);margin-top:1px;}
.sm-cell{width:52px;height:32px;text-align:center;border-bottom:1px solid var(--border-soft);transition:background 0.1s;vertical-align:middle;}
.sm-cell-0{background:transparent;}
.sm-cell-1{background:rgba(94,227,161,0.10);}
.sm-cell-2{background:rgba(94,227,161,0.25);}
.sm-cell-3{background:rgba(94,227,161,0.48);}
.sm-cell-red.sm-cell-1{background:rgba(255,107,107,0.09);}
.sm-cell-red.sm-cell-2{background:rgba(255,107,107,0.20);}
.sm-cell-red.sm-cell-3{background:rgba(255,107,107,0.38);}
.sm-cell-conv{width:48px;text-align:center;border-bottom:1px solid var(--border-soft);padding:0 4px;}
.sm-conv-n{font-size:10px;color:var(--text-faint);font-family:var(--font-mono);}
.sm-conv-n[data-n="5"],.sm-conv-n[data-n="4"]{color:var(--accent);}
.sm-conv-n[data-n="3"]{color:var(--text);}
.sm-empty{padding:32px 20px;text-align:center;color:var(--text-faint);font-size:12px;line-height:1.8;}
.sm-cell-star{width:32px;text-align:center;cursor:pointer;border-bottom:1px solid var(--border-soft);font-size:13px;line-height:32px;color:var(--text-faint);}
.sm-cell-star:hover{background:rgba(255,200,87,0.08);}
.sm-cell-star.fav{color:var(--warn,#ffc857);}
`;

  function injectCSS() {
    if (document.getElementById(CSS_ID)) return;
    const s = document.createElement('style');
    s.id = CSS_ID; s.textContent = CSS;
    document.head.appendChild(s);
  }

  const MODULE = {
    _container: null,
    _data: null,
    _sortCol: 'conv',
    _sortDir: -1,
    _filterSetup: 'all',

    mount(container) {
      if (!container) return;
      injectCSS();
      this._container = container;
      this._data = null;
      container.innerHTML = `
        <div class="sm-module">
          <div class="sm-head">
            <div class="sm-title">Signal Matrix</div>
            <div class="sm-controls">
              <button class="sm-refresh" id="sm-refresh" title="Refresh">↻</button>
            </div>
          </div>
          <div class="sm-table-wrap" id="sm-table-wrap">
            <div class="sm-empty">Loading…</div>
          </div>
        </div>`;

      container.querySelectorAll('.sm-filter').forEach(btn => {
        btn.addEventListener('click', () => {
          container.querySelectorAll('.sm-filter').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          this._filterSetup = btn.dataset.filter;
          this._render();
        });
      });
      container.querySelector('#sm-refresh')?.addEventListener('click', () => this.load());
      this.load();
    },

    async load(dateStr) {
      const url = dateStr ? `/api/signals/matrix?date=${dateStr}` : '/api/signals/matrix';
      const wrap = this._container?.querySelector('#sm-table-wrap');
      try {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(resp.status);
        this._data = await resp.json();
        this._render();
      } catch(e) {
        if (wrap) wrap.innerHTML = `<div class="sm-empty">No signal data.<br><span style="font-size:10px;color:var(--text-faint)">Run a daily scan to populate.</span></div>`;
      }
    },

    _render() {
      const wrap = this._container?.querySelector('#sm-table-wrap');
      if (!wrap || !this._data) return;

      let rows = [...(this._data.rows || [])];

      if (this._filterSetup === 'dormant') {
        rows = rows.filter(r => (r.dormant_str || 0) > 0.5);
      } else if (this._filterSetup !== 'all') {
        rows = rows.filter(r => r.setup_type === this._filterSetup);
      }

      if (!rows.length) {
        wrap.innerHTML = '<div class="sm-empty">No tickers match filter.<br><span style="font-size:10px;color:var(--text-faint)">Run a daily scan to populate.</span></div>';
        return;
      }

      const col = this._sortCol, dir = this._sortDir;
      const STR = { conv: 'conviction', macro: 'macro_str', ta: 'ta_str', gex: 'gex_str', flow: 'flow_str', dorm: 'dormant_str', sent: 'sentiment_str' };
      rows.sort((a, b) => {
        const key = STR[col] || 'factors_firing';
        return dir * (((b[key] || 0)) - ((a[key] || 0)));
      });

      const self = this;
      const _cell = (str, label, isRed) => {
        const lvl = !str || str < 0.05 ? 0 : str < 1.0 ? 1 : str < 2.0 ? 2 : 3;
        const cls = (isRed && lvl > 0) ? `sm-cell sm-cell-red sm-cell-${lvl}` : `sm-cell sm-cell-${lvl}`;
        return `<td class="${cls}" title="${label || ''}"></td>`;
      };
      const _th = (id, lbl) => {
        const active = self._sortCol === id ? ' sm-th-active' : '';
        const arrow = self._sortCol === id ? (self._sortDir < 0 ? ' ▾' : ' ▴') : '';
        return `<th class="sm-th${active}" data-sort="${id}">${lbl}${arrow}</th>`;
      };

      const favs = new Set(JSON.parse(localStorage.getItem('ev-favorites') || '[]'));

      let html = `<table class="sm-table">
        <thead><tr>
          <th class="sm-th sm-th-ticker">TICKER</th>
          ${_th('macro','MACRO')}${_th('ta','TA')}${_th('gex','GEX')}
          ${_th('flow','FLOW')}${_th('dorm','DORM')}${_th('sent','SENT')}
          ${_th('conv','CONV')}
          <th class="sm-th" style="width:32px">★</th>
        </tr></thead><tbody>`;

      rows.forEach(r => {
        const pickBadge = r.in_picks ? '<span class="sm-pick-badge">PICK</span>' : '';
        const gexRed = r.gex_label === 'long_gamma';
        const macroRed = (r.macro_str || 0) < 0.5;
        const isFav = favs.has(r.ticker);
        html += `<tr class="sm-row${r.in_picks ? ' sm-row-pick' : ''}" data-sm-ticker="${r.ticker}">
          <td class="sm-td-ticker">
            <div class="sm-ticker">${r.ticker} ${pickBadge}</div>
          </td>
          ${_cell(r.macro_str, 'Macro', macroRed)}
          ${_cell(r.ta_str, r.ta_label, false)}
          ${_cell(r.gex_str, r.gex_label, gexRed)}
          ${_cell(r.flow_str, r.flow_label, false)}
          ${_cell(r.dormant_str, r.dormant_label, false)}
          ${_cell(r.sentiment_str, r.sentiment_label, false)}
          <td class="sm-cell-conv"><span class="sm-conv-n" data-n="${r.conviction||0}">${r.conviction||0}/5</span></td>
          <td class="sm-cell-star${isFav ? ' fav' : ''}" data-sm-star="${r.ticker}">${isFav ? '★' : '☆'}</td>
        </tr>`;
      });

      html += '</tbody></table>';
      wrap.innerHTML = html;

      wrap.querySelectorAll('.sm-th[data-sort]').forEach(th => {
        th.addEventListener('click', () => {
          if (self._sortCol === th.dataset.sort) self._sortDir *= -1;
          else { self._sortCol = th.dataset.sort; self._sortDir = -1; }
          self._render();
        });
      });

      wrap.querySelectorAll('.sm-row').forEach(row => {
        row.addEventListener('click', () => {
          if (window.EV) window.EV.Store.set('selectedTicker', row.dataset.smTicker);
        });
      });

      wrap.querySelectorAll('.sm-cell-star').forEach(cell => {
        cell.addEventListener('click', (e) => {
          e.stopPropagation();
          const ticker = cell.dataset.smStar;
          const cur = new Set(JSON.parse(localStorage.getItem('ev-favorites') || '[]'));
          if (cur.has(ticker)) cur.delete(ticker); else cur.add(ticker);
          localStorage.setItem('ev-favorites', JSON.stringify([...cur]));
          cell.classList.toggle('fav', cur.has(ticker));
          cell.textContent = cur.has(ticker) ? '★' : '☆';
        });
      });
    },

    unmount() {
      if (this._container) this._container.innerHTML = '';
      this._data = null; this._container = null;
    },

    resize() {},
  };

  window.EV_SignalMatrix = MODULE;
  window.EV_FactorPulse  = MODULE; // backward compat
})();
