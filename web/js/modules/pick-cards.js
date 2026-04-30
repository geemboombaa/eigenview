(() => {
  const CSS_ID = 'ev-pick-cards-css';
  const CSS = `
.pc-module{display:flex;flex-direction:column;height:100%;}
.pc-head{display:flex;align-items:center;justify-content:space-between;padding:14px 16px 10px;flex-shrink:0;}
.pc-title{display:flex;align-items:baseline;gap:10px;}
.pc-h{font-family:var(--font-display,Georgia,serif);font-size:17px;font-weight:500;}
.pc-sub{color:var(--text-faint);font-size:11px;}
.pc-acts{display:flex;gap:6px;align-items:center;}
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
/* Actions — hidden until hover */
.card-actions{display:flex;gap:6px;padding:2px 14px 12px;opacity:0;transition:opacity .15s;}
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
`;

  function injectCSS() {
    if (document.getElementById(CSS_ID)) return;
    const s = document.createElement('style');
    s.id = CSS_ID;
    s.textContent = CSS;
    document.head.appendChild(s);
  }

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

  function chipHtml(facs) {
    if (!facs) return '';
    const chips = [];
    if (facs.technical?.firing) {
      const lbl = facs.technical.label ? ` ${facs.technical.label}` : '';
      chips.push(`<span class="chip active-chip">✓ TA${lbl}</span>`);
    }
    if (facs.gex?.firing) {
      chips.push(`<span class="chip active-chip">✓ GEX ${facs.gex.label || ''}</span>`);
    }
    if (facs.flow?.firing) {
      chips.push(`<span class="chip active-chip">✓ FLOW ${facs.flow.label || ''}</span>`);
    }
    if (facs.dormant?.firing) {
      const pct = Math.round((facs.dormant.strength || 0) * 100);
      chips.push(`<span class="chip dormant">◈ DORMANT ${pct}%</span>`);
    } else if (facs.dormant?.label === 'ACCUMULATING') {
      chips.push(`<span class="chip">◈ ACCUMULATING</span>`);
    }
    if (facs.sentiment?.firing) {
      chips.push(`<span class="chip novelty">● SENTIMENT ${facs.sentiment.label || ''}</span>`);
    }
    return chips.join('');
  }

  function cardHtml(p) {
    const dir = (p.direction || 'long').toLowerCase();
    const struct = p.structure;
    const macro = p.factors?.macro_regime;
    const cautionFlag = macro && !macro.firing ? ' <span class="caution-badge">CAUTION</span>' : '';

    return `
<div class="pick-card" data-ticker="${p.ticker}" data-dir="${dir}">
  <div class="card-row1">
    <div class="card-id">
      <span class="card-ticker">${p.ticker}${cautionFlag}</span>
      <span class="direction-tag tag-${dir}">${dir.toUpperCase()}</span>
    </div>
    <div class="card-conv">
      <div class="conv-dots">${convDots(p.conviction || 0)}</div>
      <span class="conv-lbl">${p.conviction || 0}/5</span>
    </div>
  </div>

  ${struct ? `
  <div class="struct-strip" data-dir="${dir}">
    <div class="struct-main">
      <span class="struct-diamond">◆</span>
      <span class="struct-desc">${struct.description || struct.type || ''}</span>
      ${struct.legs ? `<span class="struct-legs">· ${struct.legs}</span>` : ''}
    </div>
    <button class="btn-why" data-ticker="${p.ticker}" data-struct="${(struct.description || struct.type || '')}">WHY?</button>
  </div>` : ''}

  <div class="thesis-block">
    <span class="ai-badge">◆ AI</span>
    <div class="thesis-text">${firstSentence(p.thesis)}</div>
  </div>

  <div class="card-meta">
    ${p.entry_low != null ? `<span>Entry <strong>$${p.entry_low}–$${p.entry_high}</strong></span>` : ''}
    ${p.stop != null ? `<span>Stop <strong>$${p.stop}</strong></span>` : ''}
    ${p.iv_rank != null ? `<span>IV Rank <strong>${p.iv_rank}</strong></span>` : ''}
  </div>

  <div class="chip-row">${chipHtml(p.factors)}</div>

  <div class="card-actions">
    <button class="pc-btn primary btn-detail" data-ticker="${p.ticker}">DETAIL →</button>
    <button class="pc-btn btn-ask-ai" data-ticker="${p.ticker}">ASK AI</button>
    <button class="pc-btn btn-pin" data-ticker="${p.ticker}">⭐</button>
    <button class="pc-btn btn-alert" data-ticker="${p.ticker}">⟁</button>
  </div>
</div>`;
  }

  function listRowHtml(p) {
    const dir = (p.direction || 'long').toLowerCase();
    return `
<div class="pick-list-row" data-ticker="${p.ticker}" data-dir="${dir}">
  <span class="plr-ticker">${p.ticker}</span>
  <span class="direction-tag tag-${dir}" style="flex-shrink:0">${dir.toUpperCase()}</span>
  <span class="plr-setup">${p.setup_type || ''} ${p.structure?.description ? '· ' + p.structure.description : ''}</span>
  <div class="plr-conv">${Array.from({length:5},(_,i)=>`<span class="plr-dot${i<(p.conviction||0)?' on':''}"></span>`).join('')}</div>
  <span class="plr-meta">$${p.entry_low}–$${p.entry_high}</span>
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

      this.el.innerHTML = `<div class="pc-module">
        <div class="pc-head">
          <div class="pc-title">
            <h2 class="pc-h">Today's Picks</h2>
            <span class="pc-sub" id="pc-sub">—</span>
          </div>
          <div class="pc-acts">
            <div class="pc-view-tog">
              <button class="pc-vtb active" data-view="cards">CARDS</button>
              <button class="pc-vtb" data-view="list">LIST</button>
            </div>
          </div>
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

      // Keyboard nav
      this._bindKeyboard();

      // Subscriptions
      this._sub('picks', picks => this._renderCards(picks));
      this._sub('activeCategory', cat => this._filterAndRender(cat));
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
    }

    _renderCards(picks) {
      this._currentPicks = picks || [];
      const body = this._qs('#pc-body');
      const sub = this._qs('#pc-sub');
      if (!body) return;

      if (!picks || !picks.length) { this._renderEmpty(); return; }

      const date = new Date().toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
      if (sub) sub.textContent = `${picks.length} pick${picks.length !== 1 ? 's' : ''} · ${date}`;

      body.innerHTML = picks.map(p =>
        this._view === 'list' ? listRowHtml(p) : cardHtml(p)
      ).join('');

      this._bindCardEvents(picks);
    }

    _renderEmpty() {
      const body = this._qs('#pc-body');
      const sub = this._qs('#pc-sub');
      if (sub) sub.textContent = 'no picks';
      if (body) body.innerHTML = `<div class="pc-empty">
        <strong>No picks today</strong>
        No tickers qualified all gates. Rare but real.<br>
        Check Signal Bench for partial fires, or wait for next scan.
      </div>`;
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

      this.el.querySelectorAll('.btn-why').forEach(btn => {
        btn.addEventListener('click', e => {
          e.stopPropagation();
          const t = btn.dataset.ticker;
          const struct = btn.dataset.struct;
          window.EV?.Store.set('chatPrefill', `Why recommend ${struct} for ${t}? What's the rationale given current IV and setup?`);
        });
      });
    }

    _selectPick(ticker, pick) {
      window.EV?.Store.set('selectedTicker', ticker);
      window.EV?.Store.set('selectedPick', pick);
      // Scroll to detail module
      const detail = document.querySelector('[data-module-id="price-chart"],[data-module-id="detail-combo"]');
      if (detail) detail.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    _filterAndRender(cat) {
      const all = window.EV?.Store.get('picks') || [];
      if (!cat || cat === 'today') { this._renderCards(all); return; }
      const map = {
        dormant: p => p.factors?.dormant?.firing,
        breakout: p => p.setup_type === 'breakout',
        pullback: p => p.setup_type === 'pullback',
        compression: p => p.setup_type === 'compression',
        earnings: p => p.factors?.sentiment?.detail?.catalyst_near,
      };
      const fn = map[cat] || (p => p.setup_type === cat);
      this._renderCards(all.filter(fn));
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
