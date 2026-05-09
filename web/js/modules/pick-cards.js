(() => {
  const CSS_ID = 'ev-pick-cards-css';
  const CSS = `
.pc-module{display:flex;flex-direction:column;height:100%;}
.pc-head{display:flex;align-items:center;justify-content:space-between;padding:14px 16px 10px;flex-shrink:0;}
.pc-title{display:flex;align-items:baseline;gap:10px;}
.pc-h{font-family:var(--font-display,Georgia,serif);font-size:17px;font-weight:500;}
.pc-sub{color:var(--text-faint);font-size:11px;}
.pc-acts{display:flex;gap:6px;align-items:center;}
.pc-date-nav{display:flex;align-items:center;gap:4px;}
.pc-date-nav button{background:transparent;border:1px solid var(--border);border-radius:3px;color:var(--text-dim);padding:3px 7px;font-size:11px;cursor:pointer;font-family:var(--font-mono);}
.pc-date-nav button:hover{color:var(--text);border-color:var(--accent-dim);}
.pc-date-nav button:disabled{opacity:0.3;cursor:default;}
.pc-date-label{font-size:10px;color:var(--text-faint);letter-spacing:0.3px;min-width:60px;text-align:center;}
.pc-demo-btn{font-size:9px;padding:3px 8px;border-radius:3px;border:1px solid var(--accent-dim);background:transparent;color:var(--accent);cursor:pointer;font-family:var(--font-mono);letter-spacing:0.8px;}
.pc-demo-btn:hover{background:rgba(94,227,161,0.08);}
.pc-view-tog{display:flex;background:var(--panel-3);border:1px solid var(--border);border-radius:5px;overflow:hidden;}
.pc-vtb{background:none;border:none;border-right:1px solid var(--border);color:var(--text-dim);padding:5px 12px;font-family:var(--font-mono,'SF Mono',monospace);font-size:10px;letter-spacing:1px;cursor:pointer;}
.pc-vtb:last-child{border-right:none;}
.pc-vtb:hover{color:var(--text);}
.pc-vtb.active{background:var(--panel);color:var(--accent);}
/* Grid */
.pc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;padding:4px 16px 16px;overflow-y:auto;}
.pc-list{display:flex;flex-direction:column;gap:6px;padding:4px 16px 16px;overflow-y:auto;}
/* Card */
.pick-card{background:var(--panel);border:1px solid var(--border);border-radius:8px;cursor:pointer;transition:border-color .12s,transform .12s,box-shadow .12s;overflow:hidden;position:relative;}
.pick-card:hover{border-color:var(--accent-dim);transform:translateY(-1px);box-shadow:var(--shadow,0 2px 12px rgba(0,0,0,0.4));}
.pick-card.selected{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent-dim);}
.pick-card[data-dir="long"]{border-left:3px solid var(--long,#5ee3a1);}
.pick-card[data-dir="short"]{border-left:3px solid var(--short,#ff6b6b);}
.pick-card[data-dir="vol"]{border-left:3px solid var(--vol,#d2a6ff);}
/* Row 1 — ticker + conviction */
.card-row1{display:flex;align-items:center;justify-content:space-between;padding:13px 14px 7px;}
.card-id{display:flex;align-items:center;gap:8px;}
.card-ticker{font-size:20px;font-weight:600;letter-spacing:.4px;}
.direction-tag{font-size:9px;padding:2px 7px;border-radius:3px;letter-spacing:1px;text-transform:uppercase;font-weight:600;}
.tag-long{color:var(--long,#5ee3a1);background:rgba(94,227,161,.12);border:1px solid rgba(94,227,161,.3);}
.tag-short{color:var(--short,#ff6b6b);background:rgba(255,107,107,.1);border:1px solid rgba(255,107,107,.3);}
.tag-vol{color:var(--vol,#d2a6ff);background:rgba(210,166,255,.1);border:1px solid rgba(210,166,255,.3);}
.card-conv{display:flex;flex-direction:column;align-items:flex-end;gap:4px;}
.conv-dots{display:flex;gap:3px;}
.conv-dot{display:inline-block;width:18px;height:4px;border-radius:2px;background:var(--chip-border,#2b3245);}
.conv-dot.on{background:var(--accent,#5ee3a1);}
.conv-lbl{font-size:10px;color:var(--text-faint);}
/* Structure strip */
.struct-strip{display:flex;align-items:center;justify-content:space-between;padding:7px 14px;border-top:1px solid var(--border-soft,#1a1e2a);border-bottom:1px solid var(--border-soft,#1a1e2a);gap:8px;}
.struct-strip[data-dir="long"]{background:rgba(94,227,161,.05);}
.struct-strip[data-dir="short"]{background:rgba(255,107,107,.05);}
.struct-strip[data-dir="vol"]{background:rgba(210,166,255,.05);}
.struct-main{display:flex;align-items:center;gap:6px;min-width:0;overflow:hidden;}
.struct-diamond{color:var(--accent,#5ee3a1);font-size:11px;flex-shrink:0;}
.struct-desc{font-size:11px;font-weight:600;color:var(--text);white-space:nowrap;flex-shrink:0;}
.struct-legs{font-size:10px;color:var(--text-dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.btn-why{font-size:9px;letter-spacing:.8px;padding:3px 8px;cursor:pointer;background:var(--panel-3,#1d2231);border:1px solid var(--chip-border,#2b3245);border-radius:3px;color:var(--text-dim);font-family:var(--font-mono,'SF Mono',monospace);flex-shrink:0;white-space:nowrap;}
.btn-why:hover{color:var(--text);border-color:var(--accent-dim);}
/* Thesis */
.thesis-block{margin:8px 14px;background:var(--panel-2,#171b26);border:1px solid var(--border-soft,#1a1e2a);border-radius:5px;padding:9px 12px;position:relative;}
.thesis-text{font-family:var(--font-prose,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif);font-size:12px;line-height:1.5;color:var(--text-dim);padding-right:32px;}
.ai-badge{position:absolute;top:7px;right:8px;font-size:8px;color:var(--vol,#d2a6ff);border:1px solid rgba(210,166,255,.35);padding:1px 4px;border-radius:2px;letter-spacing:1.5px;}
/* Meta row */
.card-meta{display:flex;gap:12px;flex-wrap:wrap;padding:5px 14px;font-size:11px;color:var(--text-dim);}
.card-meta strong{color:var(--text);}
/* Chips */
.chip-row{display:flex;flex-wrap:wrap;gap:5px;padding:4px 14px 8px;}
.chip{font-size:9px;padding:3px 7px;background:var(--chip-bg,#1d2231);border:1px solid var(--chip-border,#2b3245);border-radius:3px;color:var(--text-dim);letter-spacing:.3px;}
.chip.active-chip{color:var(--accent,#5ee3a1);border-color:rgba(94,227,161,.3);background:rgba(94,227,161,.06);}
.chip.dormant{color:var(--warn,#ffc857);border-color:rgba(255,200,87,.35);background:rgba(255,200,87,.06);}
.chip.novelty{color:var(--vol,#d2a6ff);border-color:rgba(210,166,255,.35);background:rgba(210,166,255,.06);}
/* Actions — always faintly visible, full on hover/selected */
.card-actions{display:flex;gap:6px;padding:2px 14px 12px;opacity:0.45;transition:opacity .15s;position:relative;z-index:2;}
.pick-card:hover .card-actions{opacity:1;}
.pick-card.selected .card-actions{opacity:1;}
.pc-btn{background:var(--panel-3,#1d2231);border:1px solid var(--border,#232836);color:var(--text-dim);padding:5px 10px;border-radius:4px;font-family:var(--font-mono,'SF Mono',monospace);font-size:9px;letter-spacing:1px;cursor:pointer;transition:color .1s,border-color .1s;}
.pc-btn:hover{color:var(--text);border-color:var(--accent-dim);}
.pc-btn.primary{color:var(--accent,#5ee3a1);border-color:rgba(94,227,161,.3);}
.pc-btn.primary:hover{background:rgba(94,227,161,.08);}
/* List view */
.pick-list-row{display:flex;align-items:center;gap:12px;background:var(--panel);border:1px solid var(--border);border-radius:6px;padding:10px 14px;cursor:pointer;transition:border-color .1s;}
.pick-list-row:hover{border-color:var(--accent-dim);}
.pick-list-row.selected{border-color:var(--accent);}
.pick-list-row[data-dir="long"]{border-left:3px solid var(--long,#5ee3a1);}
.pick-list-row[data-dir="short"]{border-left:3px solid var(--short,#ff6b6b);}
.pick-list-row[data-dir="vol"]{border-left:3px solid var(--vol,#d2a6ff);}
.plr-ticker{font-size:14px;font-weight:600;width:60px;flex-shrink:0;}
.plr-setup{font-size:11px;color:var(--text-dim);flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.plr-conv{display:flex;gap:2px;flex-shrink:0;}
.plr-dot{width:12px;height:3px;border-radius:2px;background:var(--chip-border);}
.plr-dot.on{background:var(--accent);}
.plr-meta{font-size:10px;color:var(--text-faint);flex-shrink:0;}
/* Empty / error */
.pc-empty{padding:32px 20px;text-align:center;color:var(--text-faint);font-size:12px;line-height:1.6;}
.pc-empty strong{display:block;color:var(--text-dim);margin-bottom:6px;font-size:13px;}
/* Caution badge on card */
.caution-badge{display:inline-block;font-size:8px;color:var(--warn);border:1px solid rgba(255,200,87,.3);background:rgba(255,200,87,.06);padding:1px 5px;border-radius:2px;letter-spacing:1px;margin-left:6px;vertical-align:middle;}
/* Filter chips bar */
.pc-filter-bar{display:flex;gap:4px;padding:4px 14px 8px;flex-wrap:wrap;flex-shrink:0;border-bottom:1px solid var(--border-soft);}
.pc-filter-chip{background:transparent;border:1px solid var(--border);color:var(--text-faint);padding:2px 8px;border-radius:3px;font-family:var(--font-mono);font-size:9px;cursor:pointer;letter-spacing:0.5px;white-space:nowrap;}
.pc-filter-chip:hover{color:var(--text);}
.pc-filter-chip.active{color:var(--accent);border-color:rgba(94,227,161,0.3);background:rgba(94,227,161,0.05);}
.pc-filter-bar.hidden{display:none;}
/* Setup name */
.card-setup-name{padding:3px 14px 0;font-size:11px;color:var(--text-dim);letter-spacing:0.3px;}
`;

  function injectCSS() {
    if (document.getElementById(CSS_ID)) return;
    const s = document.createElement('style');
    s.id = CSS_ID;
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  // ── pattern human names ──────────────────────────────────────────────────
  const PATTERN_NAMES = {
    breakout: 'Breakout',
    pullback_in_trend: 'Pullback to Support',
    compression_break: 'Compression Break',
    ema_reclaim: 'EMA Reclaim',
    base_breakout: 'Base Breakout',
    oversold_bounce: 'Oversold Bounce',
    failed_breakdown: 'Failed Breakdown',
    bullish_reversal: 'Bullish Reversal',
    bearish_reversal: 'Bearish Reversal',
    breakdown: 'Breakdown',
    rally_in_downtrend: 'Short Rally',
    compression_break_down: 'Compression Break Down',
    ema_rejection: 'EMA Rejection',
    base_breakdown: 'Base Breakdown',
    overbought_reversal: 'Overbought Reversal',
    failed_breakout: 'Failed Breakout',
  };

  // ── helpers ──────────────────────────────────────────────────────────────
  function firstSentence(text) {
    if (!text) return '—';
    const m = text.match(/^.+?[.!?](?:\s|$)/);
    return m ? m[0].trim() : text.slice(0, 120) + (text.length > 120 ? '…' : '');
  }

  function fmt(n, prefix = '$') {
    if (n == null) return '—';
    return `${prefix}${Number(n).toLocaleString()}`;
  }

  function convDots(n) {
    return Array.from({ length: 5 }, (_, i) =>
      `<span class="conv-dot${i < n ? ' on' : ''}"></span>`
    ).join('');
  }

  function cardHtml(p, isFav = false) {
    const dir = (p.direction || 'long').toLowerCase();
    const macro = p.factors?.macro_regime;
    const caution = macro && !macro.firing ? ' <span class="caution-badge">CAUTION</span>' : '';
    const setupName = PATTERN_NAMES[p.setup_type] || (p.setup_type || '').replace(/_/g, ' ');

    return `
<div class="pick-card" data-ticker="${p.ticker}" data-dir="${dir}">
  <div class="card-row1">
    <div class="card-id">
      <span class="card-ticker">${p.ticker}</span>
      <span class="direction-tag tag-${dir}">${dir.toUpperCase()}</span>
      ${caution}
    </div>
    <div class="card-conv">
      <div class="conv-dots">${convDots(p.conviction || 0)}</div>
      <span class="conv-lbl">${p.conviction || 0}/5</span>
    </div>
  </div>

  <div class="card-setup-name">${setupName}${p.structure?.description ? ` · <span class="card-rec">${p.structure.description}</span>` : ''}</div>

  <div class="thesis-block">
    <span class="ai-badge">◆ AI</span>
    <div class="thesis-text">${firstSentence(p.thesis)}</div>
  </div>

  <div class="card-meta">
    ${p.entry_low != null ? `<span>Entry <strong>$${p.entry_low}–$${p.entry_high}</strong></span>` : ''}
    ${p.stop != null ? `<span>Stop <strong>$${p.stop}</strong></span>` : ''}
  </div>

  <div class="card-actions">
    <button class="pc-btn primary btn-detail" data-ticker="${p.ticker}">DETAIL →</button>
    <button class="pc-btn btn-ask-ai" data-ticker="${p.ticker}">ASK AI</button>
    <button class="pc-btn btn-pin${isFav ? ' active' : ''}" data-ticker="${p.ticker}" title="${isFav ? 'Remove from My List' : 'Add to My List'}">${isFav ? '★' : '☆'}</button>
  </div>
</div>`;
  }

  function listRowHtml(p, isFav = false) {
    const dir = (p.direction || 'long').toLowerCase();
    const setupName = PATTERN_NAMES[p.setup_type] || (p.setup_type || '').replace(/_/g, ' ');
    const entry = p.entry_low != null ? `$${p.entry_low}–$${p.entry_high}` : '';
    return `
<div class="pick-list-row" data-ticker="${p.ticker}" data-dir="${dir}">
  <span class="plr-ticker">${p.ticker}</span>
  <span class="direction-tag tag-${dir}" style="flex-shrink:0">${dir.toUpperCase()}</span>
  <span class="plr-setup">${setupName}</span>
  <div class="plr-conv">${Array.from({length:5},(_,i)=>`<span class="plr-dot${i<(p.conviction||0)?' on':''}"></span>`).join('')}</div>
  <span class="plr-meta">${entry}</span>
  <button class="pc-btn btn-pin${isFav ? ' active' : ''}" data-ticker="${p.ticker}" style="font-size:12px;padding:2px 6px" title="${isFav ? 'Remove from My List' : 'Add to My List'}">${isFav ? '★' : '☆'}</button>
</div>`;
  }

  // ── module class ──────────────────────────────────────────────────────────
  const BaseClass = (window.EV && window.EV.Module) || class {
    constructor(el, cfg) { this.el = el; this.config = cfg || {}; this._unsubs = []; }
    unmount() { this._unsubs.forEach(f => f()); this._unsubs = []; }
    _sub(k, f) { if (window.EV) this._unsubs.push(window.EV.Store.subscribe(k, f)); }
    _qs(sel) { return this.el.querySelector(sel); }
    _qsa(sel) { return this.el.querySelectorAll(sel); }
  };

  class PickCardsModule extends BaseClass {
    mount() {
      injectCSS();
      this._view = 'cards';
      this._currentPicks = [];
      this._selectedTicker = window.EV?.Store.get('selectedTicker') || null;
      this._availableDates = [];
      this._dateIdx = 0;
      this._activeSetupFilter = 'all';
      this._favorites = new Set(JSON.parse(localStorage.getItem('ev-favorites') || '[]'));

      this.el.innerHTML = `<div class="pc-module">
        <div class="pc-head" id="pc-head-bar">
          <div class="pc-acts">
            <div class="pc-date-nav" id="pc-date-nav">
              <button id="pc-prev-date" title="Previous day" disabled>◀</button>
              <span class="pc-date-label" id="pc-date-label">TODAY</span>
              <button id="pc-next-date" title="Next day" disabled>▶</button>
            </div>
            <div class="pc-view-tog">
              <button class="pc-vtb active" data-view="cards">CARDS</button>
              <button class="pc-vtb" data-view="list">LIST</button>
            </div>
          </div>
          <span class="pc-sub" id="pc-sub">—</span>
        </div>
        <div id="pc-body" class="pc-grid"></div>
      </div>`;

      // View toggle
      this.el.querySelectorAll('.pc-vtb').forEach(btn => {
        btn.addEventListener('click', () => {
          this.el.querySelectorAll('.pc-vtb').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          this._view = btn.dataset.view;
          const body = this._qs('#pc-body');
          if (body) body.className = this._view === 'list' ? 'pc-list' : 'pc-grid';
          this._renderCards(this._currentPicks);
        });
      });

      // Date navigation
      this._qs('#pc-prev-date').addEventListener('click', async () => {
        if (this._dateIdx < this._availableDates.length - 1) {
          this._dateIdx++;
          this._updateDateNav();
          await this._loadPicksForDate(this._availableDates[this._dateIdx]);
        }
      });
      this._qs('#pc-next-date').addEventListener('click', async () => {
        if (this._dateIdx > 0) {
          this._dateIdx--;
          this._updateDateNav();
          await this._loadPicksForDate(this._availableDates[this._dateIdx]);
        }
      });

      // Keyboard nav
      this._bindKeyboard();

      // Subscriptions
      this._sub('picks', picks => this._renderCards(picks));
      this._sub('selectedTicker', t => {
        this._selectedTicker = t;
        this.el.querySelectorAll('.pick-card,.pick-list-row').forEach(c => {
          c.classList.toggle('selected', c.dataset.ticker === t);
        });
      });

      // Initial render
      const picks = window.EV?.Store.get('picks');
      if (picks && picks.length) this._renderCards(picks);
      else this._renderEmpty();

      // Load available dates asynchronously
      this._loadDates();
    }

    _renderCards(picks, subtitle) {
      this._currentPicks = picks || [];
      const body = this._qs('#pc-body');
      const sub = this._qs('#pc-sub');
      if (!body) return;

      if (!picks || !picks.length) { this._renderEmpty(); return; }

      if (sub && subtitle !== undefined) sub.textContent = subtitle;
      else if (sub) sub.textContent = `${picks.length} pick${picks.length !== 1 ? 's' : ''}`;

      // Apply favorites star state
      const favSet = this._favorites;
      body.innerHTML = picks.map(p =>
        this._view === 'list' ? listRowHtml(p, favSet.has(p.ticker)) : cardHtml(p, favSet.has(p.ticker))
      ).join('');

      this._bindCardEvents(picks);
    }

    _applySetupFilter() {
      const all = this._currentPicks;
      if (this._activeSetupFilter === 'all') {
        this._renderCards(all);
        return;
      }
      if (this._activeSetupFilter === 'dormant') {
        this._renderCards(all.filter(p => p.factors?.dormant?.firing));
        return;
      }
      if (this._activeSetupFilter === 'earnings') {
        this._renderCards(all.filter(p => p.factors?.sentiment?.detail?.catalyst_near));
        return;
      }
      this._renderCards(all.filter(p => p.setup_type === this._activeSetupFilter));
    }

    _renderEmpty() {
      const body = this._qs('#pc-body');
      const sub = this._qs('#pc-sub');
      if (sub) sub.textContent = 'no picks';
      if (body) body.innerHTML = `<div class="pc-empty">
        <strong>No picks today</strong>
        No tickers qualified all gates. Rare but real.<br>
        Check Signal Bench for partial fires, or wait for next scan.
        <br><br>
        <button class="pc-demo-btn" id="pc-demo-btn">▶ LOAD DEMO</button>
      </div>`;
      this._qs('#pc-demo-btn')?.addEventListener('click', () => this._loadDemo());
    }

    _bindCardEvents(picks) {
      const findPick = t => picks.find(p => p.ticker === t);

      this.el.querySelectorAll('.pick-card').forEach(card => {
        const t = card.dataset.ticker;
        card.addEventListener('click', e => {
          if (e.target.closest('.card-actions') || e.target.closest('.btn-why')) return;
          this._selectPick(t, findPick(t));
        });
      });

      this.el.querySelectorAll('.pick-list-row').forEach(row => {
        const t = row.dataset.ticker;
        row.addEventListener('click', () => this._selectPick(t, findPick(t)));
      });

      this.el.querySelectorAll('.btn-detail').forEach(btn => {
        btn.addEventListener('click', e => {
          e.stopPropagation();
          this._selectPick(btn.dataset.ticker, findPick(btn.dataset.ticker));
        });
      });

      this.el.querySelectorAll('.btn-ask-ai').forEach(btn => {
        btn.addEventListener('click', e => {
          e.stopPropagation();
          const t = btn.dataset.ticker;
          window.EV?.Store.set('chatPrefill', `Why is ${t} a pick today?`);
        });
      });

      this.el.querySelectorAll('.btn-pin').forEach(btn => {
        btn.addEventListener('click', e => {
          e.stopPropagation();
          const t = btn.dataset.ticker;
          if (this._favorites.has(t)) this._favorites.delete(t);
          else this._favorites.add(t);
          localStorage.setItem('ev-favorites', JSON.stringify([...this._favorites]));
          const allPicks = window.EV?.Store.get('picks') || this._currentPicks;
          const favPicks = {};
          this._favorites.forEach(ft => {
            const p = allPicks.find(pp => pp.ticker === ft);
            if (p) favPicks[ft] = p;
          });
          localStorage.setItem('ev-fav-picks', JSON.stringify(favPicks));
          this._renderCards(this._currentPicks);
        });
      });

    }

    _selectPick(ticker, pick) {
      window.EV?.Store.set('selectedTicker', ticker);
      window.EV?.Store.set('selectedPick', pick);
      // Scroll to detail module
      const detail = document.querySelector('[data-module-type="price-chart"],[data-module-type="factor-strip"]');
      if (detail) detail.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    _bindKeyboard() {
      let idx = 0;
      document.addEventListener('keydown', e => {
        if (['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return;
        const cards = [...this.el.querySelectorAll('.pick-card,.pick-list-row')];
        if (!cards.length) return;
        if (e.key === 'ArrowDown') { e.preventDefault(); idx = Math.min(idx + 1, cards.length - 1); cards[idx].click(); }
        if (e.key === 'ArrowUp') { e.preventDefault(); idx = Math.max(idx - 1, 0); cards[idx].click(); }
        if (e.key === 'Enter' && document.activeElement?.classList?.contains('pick-card')) {
          document.activeElement.click();
        }
      });
    }

    async _loadDates() {
      try {
        const dates = await window.EV?.API.get('/api/picks/dates');
        if (!dates || !dates.length) return;
        this._availableDates = dates; // most-recent-first from API
        this._dateIdx = 0;
        this._updateDateNav();
        // If no picks loaded yet, fetch most recent date
        const today = new Date().toISOString().slice(0, 10);
        if (!window.EV?.Store.get('picks')?.length && dates[0] !== today) {
          await this._loadPicksForDate(dates[0]);
        }
      } catch (_) {}
    }

    async _loadPicksForDate(dateStr) {
      try {
        const picks = await window.EV?.API.get(`/api/picks?date=${dateStr}`);
        this._renderCards(picks || []);
        const today = new Date().toISOString().slice(0, 10);
        const lbl = this._qs('#pc-date-label');
        if (lbl) lbl.textContent = dateStr === today ? 'TODAY' : dateStr.slice(5);
      } catch (_) {
        this._renderEmpty();
      }
    }

    _updateDateNav() {
      const prev = this._qs('#pc-prev-date');
      const next = this._qs('#pc-next-date');
      const lbl = this._qs('#pc-date-label');
      const dates = this._availableDates;
      if (prev) prev.disabled = this._dateIdx >= dates.length - 1;
      if (next) next.disabled = this._dateIdx <= 0;
      if (lbl && dates.length) {
        const today = new Date().toISOString().slice(0, 10);
        const d = dates[this._dateIdx];
        lbl.textContent = d === today ? 'TODAY' : d.slice(5);
      }
    }

    _loadDemo() {
      const demo = [
        {
          ticker: 'NVDA', date: new Date().toISOString().slice(0, 10), conviction: 5,
          setup_type: 'breakout', direction: 'long',
          entry_low: 875, entry_high: 892, stop: 848,
          thesis: 'NVDA holding above Q1 channel breakout with dealer gamma flip confirmed above $880. Unusual call flow at $900 strike signals institutional positioning ahead of AI capex cycle.',
          spot: 884.20, iv_rank: 32,
          structure: { type: 'bull_call_spread', description: 'Bull Call Spread', legs: 'Buy $880C / Sell $910C, 3 weeks', rationale: 'IV rank 32 — cheap spread captures momentum' },
          factors: {
            macro_regime: { firing: true, strength: 0.78, label: 'BULL', detail: { regime: 'bull', vix: 16.2, spy_trend: 'above_50d', breadth: 0.71 } },
            technical: { firing: true, strength: 0.85, label: 'BREAKOUT', detail: { direction: 'long', pattern: 'bull_flag', rsi: 58.3, adx: 34.2, atr_rank: 0.72, ma20_cross: 'above', volume_ratio: 1.84 } },
            gex: { firing: true, strength: 0.80, label: 'FLIP ↑', detail: { gamma_flip: 880.0, call_wall: 900.0, put_wall: 850.0, net_gex: 2.3, regime: 'positive' } },
            flow: { firing: true, strength: 0.76, label: 'UNUSUAL', detail: { premium_usd: 4200000, call_put_ratio: 3.2, aggressive_side: 'call', unusual_score: 0.82, largest_strike: 900 } },
            dormant: { firing: false, strength: 0.18, label: '—', detail: { position_age_days: 8, open_interest_rank: 0.22, activation_score: 0.18 } },
            sentiment: { firing: true, strength: 0.79, label: 'NOVELTY', detail: { novelty_score: 0.78, catalyst_near: false, news_sentiment: 0.65, embedding_distance: 0.82 } },
          }
        },
        {
          ticker: 'META', date: new Date().toISOString().slice(0, 10), conviction: 4,
          setup_type: 'pullback', direction: 'long',
          entry_low: 498, entry_high: 510, stop: 482,
          thesis: 'META pulling back to 50-day after earnings gap. GEX support band at $500 with call wall at $520 creates defined risk zone. Flow shows smart money reloading on dip.',
          spot: 503.60, iv_rank: 28,
          structure: { type: 'long_call', description: 'Long Call', legs: 'Buy $500C, 4 weeks', rationale: 'Low IV rank 28, pullback entry' },
          factors: {
            macro_regime: { firing: true, strength: 0.78, label: 'BULL', detail: { regime: 'bull', vix: 16.2, spy_trend: 'above_50d', breadth: 0.71 } },
            technical: { firing: true, strength: 0.72, label: 'PULLBACK', detail: { direction: 'long', pattern: 'pullback_50d', rsi: 44.1, adx: 28.5, atr_rank: 0.55, ma20_cross: 'below', volume_ratio: 0.92 } },
            gex: { firing: true, strength: 0.68, label: 'SUPPORT', detail: { gamma_flip: 495.0, call_wall: 520.0, put_wall: 480.0, net_gex: 1.4, regime: 'positive' } },
            flow: { firing: true, strength: 0.81, label: 'SWEEP', detail: { premium_usd: 2800000, call_put_ratio: 2.8, aggressive_side: 'call', unusual_score: 0.75, largest_strike: 520 } },
            dormant: { firing: false, strength: 0.12, label: '—', detail: { position_age_days: 3, open_interest_rank: 0.18, activation_score: 0.12 } },
            sentiment: { firing: false, strength: 0.31, label: '—', detail: { novelty_score: 0.31, catalyst_near: false, news_sentiment: 0.48, embedding_distance: 0.44 } },
          }
        },
        {
          ticker: 'TSLA', date: new Date().toISOString().slice(0, 10), conviction: 3,
          setup_type: 'compression', direction: 'long',
          entry_low: 248, entry_high: 258, stop: 235,
          thesis: 'TSLA forming weekly compression coil above $240 support. ATR contracting for 18 sessions. GEX neutral to positive above $250 with dormant position activating.',
          spot: 252.10, iv_rank: 41,
          structure: { type: 'bull_call_spread', description: 'Bull Call Spread', legs: 'Buy $255C / Sell $270C, 2 weeks', rationale: 'IV rank 41 — spread preferred over outright call' },
          factors: {
            macro_regime: { firing: true, strength: 0.78, label: 'BULL', detail: { regime: 'bull', vix: 16.2, spy_trend: 'above_50d', breadth: 0.71 } },
            technical: { firing: true, strength: 0.61, label: 'COMPRESSION', detail: { direction: 'long', pattern: 'compression_coil', rsi: 49.8, adx: 18.4, atr_rank: 0.23, ma20_cross: 'above', volume_ratio: 0.61 } },
            gex: { firing: true, strength: 0.55, label: 'NEUTRAL', detail: { gamma_flip: 250.0, call_wall: 270.0, put_wall: 230.0, net_gex: 0.4, regime: 'neutral' } },
            flow: { firing: false, strength: 0.29, label: '—', detail: { premium_usd: 480000, call_put_ratio: 1.1, aggressive_side: 'mixed', unusual_score: 0.29, largest_strike: 260 } },
            dormant: { firing: true, strength: 0.72, label: 'ACTIVATING', detail: { position_age_days: 45, open_interest_rank: 0.91, activation_score: 0.72 } },
            sentiment: { firing: false, strength: 0.24, label: '—', detail: { novelty_score: 0.24, catalyst_near: false, news_sentiment: 0.38, embedding_distance: 0.35 } },
          }
        }
      ];
      window.EV?.Store.set('picks', demo);
    }

    resize(size) {
      const body = this._qs('#pc-body');
      if (!body || this._view !== 'cards') return;
      // S: single column, M: auto minmax 280, L/XL: auto minmax 300
      const minW = size === 'S' ? '100%' : size === 'M' ? '280px' : '300px';
      body.style.gridTemplateColumns = size === 'S' ? '1fr' : `repeat(auto-fill,minmax(${minW},1fr))`;
    }
  }

  PickCardsModule.id = 'pick-cards';
  PickCardsModule.label = 'Pick Cards';
  PickCardsModule.defaultSize = 'L';
  PickCardsModule.supportedSizes = ['S', 'M', 'L', 'XL'];

  if (window.EV && window.EV.registry) {
    window.EV.registry.register(PickCardsModule);
  }
  window.PickCardsModule = PickCardsModule;
})();
