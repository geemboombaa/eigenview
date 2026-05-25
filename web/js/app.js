(function () {
  'use strict';

  const THEMES = ['dark', 'light', 'glass', 'bento'];
  let themeIdx = 3;

  function setTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    document.querySelectorAll('.theme-btn').forEach(b =>
      b.classList.toggle('active', b.dataset.theme === t)
    );
    themeIdx = THEMES.indexOf(t);
    if (themeIdx < 0) themeIdx = 0;
  }

  function cycleTheme() {
    themeIdx = (themeIdx + 1) % THEMES.length;
    setTheme(THEMES[themeIdx]);
  }

  function inputFocused() {
    const el = document.activeElement;
    return el && ['INPUT', 'TEXTAREA'].includes(el.tagName);
  }

  async function init() {
    // Templates
    EV_Templates.init();

    // Mount category nav (horizontal in subnav bar)
    const navSlot = document.getElementById('ev-nav-slot');
    if (navSlot) EV.Canvas.mountModule('category-nav', navSlot, { slot: 'nav', horizontal: true });

    // Mount market context in subnav right side
    const marketSlot = document.getElementById('ev-market-slot');
    if (marketSlot) EV.Canvas.mountModule('market-context', marketSlot, { slot: 'market' });

    // Mount pick cards in dedicated left column (PICKS tab)
    const picksContent = document.getElementById('ev-picks-content');
    if (picksContent) EV.Canvas.mountModule('pick-cards', picksContent, { slot: 'picks' });

    // Wire category nav → left-pane content switching
    const matrixContent = document.getElementById('ev-matrix-content');
    const mineContent = document.getElementById('ev-mine-content');
    let _matrixMounted = false;
    EV.Store.subscribe('activeCategory', cat => {
      [picksContent, matrixContent, mineContent].forEach(p => { if (p) p.style.display = 'none'; });
      if (!cat || cat === 'today') {
        if (picksContent) picksContent.style.display = '';
      } else if (cat === 'matrix') {
        if (matrixContent) {
          matrixContent.style.display = '';
          if (!_matrixMounted && window.EV_SignalMatrix) {
            window.EV_SignalMatrix.mount(matrixContent);
            _matrixMounted = true;
          } else {
            window.EV_SignalMatrix?.load?.();
          }
        }
      } else if (cat === 'mine') {
        if (mineContent) { mineContent.style.display = ''; _renderMine(mineContent); }
      }
    });

    function _renderMine(container) {
      const favs = new Set(JSON.parse(localStorage.getItem('ev-favorites') || '[]'));
      const allPicks = EV.Store.get('picks') || [];
      const favPicks = allPicks.filter(p => favs.has(p.ticker));
      if (!favPicks.length) {
        container.innerHTML = '<div style="padding:32px 16px;text-align:center;color:var(--text-faint);font-size:12px;line-height:1.6"><strong style="display:block;color:var(--text-dim);margin-bottom:6px">Nothing saved yet</strong>Click ☆ on any pick card to add it here.</div>';
        return;
      }
      container.innerHTML = '<div style="display:flex;flex-direction:column;gap:6px;padding:12px 14px;overflow-y:auto;height:100%">' +
        favPicks.map(p => {
          const dir = (p.direction || 'long').toLowerCase();
          const entry = p.entry_low != null ? `$${p.entry_low}–$${p.entry_high}` : '';
          return `<div class="pick-list-row" data-ticker="${p.ticker}" data-dir="${dir}" style="cursor:pointer">
            <span class="plr-ticker">${p.ticker}</span>
            <span class="direction-tag tag-${dir}" style="font-size:9px;flex-shrink:0">${dir.toUpperCase()}</span>
            <span class="plr-setup">${(p.setup_type||'').replace(/_/g,' ')}</span>
            <span class="plr-meta">${entry}</span>
            <div class="plr-conv">${Array.from({length:5},(_,i)=>`<span class="plr-dot${i<(p.conviction||0)?' on':''}"></span>`).join('')}</div>
          </div>`;
        }).join('') + '</div>';
      container.querySelectorAll('[data-ticker]').forEach(el => {
        el.addEventListener('click', () => EV.Store.set('selectedTicker', el.dataset.ticker));
      });
    }

    // Mount price chart in main canvas
    const canvas = document.getElementById('ev-canvas');
    const chartEl = document.createElement('div');
    canvas.appendChild(chartEl);
    EV.Canvas.mountModule('price-chart', chartEl);

    // Mount factor strip in child div so [data-module-type="factor-strip"] is always
    // 230px tall (for ≥80px test), while the outer #ev-strip-slot collapses to 44px
    const stripSlot = document.getElementById('ev-strip-slot');
    if (stripSlot) {
      const stripInner = document.createElement('div');
      stripInner.className = 'strip-module-inner';
      stripSlot.appendChild(stripInner);
      EV.Canvas.mountModule('factor-strip', stripInner, { slot: 'strip' });
    }

    // Mount chat
    const chatSlot = document.getElementById('ev-chat-slot');
    if (chatSlot) EV.Canvas.mountModule('ai-chat', chatSlot, { slot: 'chat' });

    // Fetch data in parallel
    const [regime, picks] = await Promise.all([
      EV.API.get('/api/market/regime'),
      EV.API.get('/api/picks')
    ]);

    if (regime) EV.Store.set('regime', regime);

    if (picks && Array.isArray(picks) && picks.length > 0) {
      EV.Store.set('picks', picks);
      const badge = document.getElementById('ev-scan-time');
      if (badge) {
        badge.textContent = `✓ ${picks.length} pick${picks.length !== 1 ? 's' : ''}`;
        badge.style.color = 'var(--accent)';
      }
    } else {
      const badge = document.getElementById('ev-scan-time');
      if (badge) badge.textContent = 'No picks today';
    }

    // Auto-refresh picks every 5 minutes
    setInterval(async () => {
      const fresh = await EV.API.get('/api/picks');
      if (fresh && Array.isArray(fresh) && fresh.length > 0) {
        EV.Store.set('picks', fresh);
        const badge = document.getElementById('ev-scan-time');
        if (badge) {
          badge.textContent = `✓ ${fresh.length} pick${fresh.length !== 1 ? 's' : ''}`;
          badge.style.color = 'var(--accent)';
        }
      }
    }, 5 * 60 * 1000);

    // SCAN button
    const scanBtn = document.getElementById('ev-scan-btn');
    if (scanBtn) {
      let _scanPoll = null;

      function _stopScanPoll() {
        if (_scanPoll) { clearInterval(_scanPoll); _scanPoll = null; }
      }

      async function _pollScanStatus() {
        const badge = document.getElementById('ev-scan-time');
        const status = await EV.API.get('/api/scan/status');
        if (!status) return;
        if (badge) badge.textContent = status.message || '…';
        if (!status.running) {
          _stopScanPoll();
          scanBtn.disabled = false;
          if (scanTest) scanTest.disabled = false;
          scanBtn.textContent = 'SCAN';
          if (status.error) {
            if (badge) { badge.textContent = 'Scan failed'; badge.style.color = 'var(--warn,#ffc857)'; }
          } else {
            if (badge) badge.style.color = status.picks > 0 ? 'var(--accent)' : 'var(--text-dim)';
            // Reload picks + matrix
            const todayStr = new Date().toISOString().slice(0, 10);
            const fresh = await EV.API.get(`/api/picks?date=${todayStr}`);
            if (fresh && fresh.length > 0) {
              EV.Store.set('picks', fresh);
              EV.Store.set('selectedPick', fresh[0]);
              if (badge) { badge.textContent = `✓ ${fresh.length} pick${fresh.length !== 1 ? 's' : ''}`; badge.style.color = 'var(--accent)'; }
            }
            window.EV_FactorPulse?.load?.();
          }
        }
      }

      // Also wire SCAN·5 quick button
      const scanTest = document.getElementById('ev-scan-test-btn');
      if (scanTest) {
        scanTest.addEventListener('click', () => {
          scanBtn.dataset.universe = 'test5';
          scanBtn.click();
          scanBtn.dataset.universe = 'ndx100';
        });
      }

      scanBtn.addEventListener('click', async () => {
        const universe = scanBtn.dataset.universe || 'ndx100';
        const badge = document.getElementById('ev-scan-time');
        scanBtn.disabled = true;
        if (scanTest) scanTest.disabled = true;
        const universeLabel = universe === 'test5' ? '5' : universe === 'ndx100' ? 'NDX100' : universe === 'sp500' ? 'SP500' : 'SP500+NDX';
        scanBtn.textContent = `SCANNING…`;
        if (badge) { badge.textContent = `Scanning ${universeLabel}…`; badge.style.color = 'var(--text-dim)'; }
        try {
          const resp = await fetch(`/api/scan?universe=${universe}`, { method: 'POST' });
          const data = await resp.json();
          if (data.status === 'already_running') {
            if (badge) badge.textContent = 'Already scanning…';
          } else if (data.status === 'too_recent') {
            scanBtn.disabled = false;
            if (scanTest) scanTest.disabled = false;
            scanBtn.textContent = 'SCAN';
            if (badge) { badge.textContent = data.message || 'Too soon'; badge.style.color = 'var(--text-dim)'; }
            return;
          }
          // Poll status every 4s regardless
          _stopScanPoll();
          _scanPoll = setInterval(_pollScanStatus, 4000);
        } catch {
          scanBtn.disabled = false;
          scanBtn.textContent = 'SCAN';
          if (badge) { badge.textContent = 'Scan failed'; badge.style.color = 'var(--warn,#ffc857)'; }
        }
      });
    }

    // Keyboard shortcuts
    document.addEventListener('keydown', e => {
      const inInput = inputFocused();

      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        document.getElementById('ev-search')?.focus();
        return;
      }
      if (e.key === '/' && !inInput) {
        e.preventDefault();
        document.querySelector('.ev-chat-textarea')?.focus();
        return;
      }
      if (e.key === 'Escape') {
        document.getElementById('ev-shortcuts-overlay').hidden = true;
        EV.Canvas.setEditMode(false);
        if (inInput) document.activeElement.blur();
        return;
      }
      if (e.key === '?' && !inInput) {
        document.getElementById('ev-shortcuts-overlay').hidden = false;
        return;
      }
      if ((e.key === 'h' || e.key === 'H') && !inInput) {
        window.EV_Help?.open('overview');
        return;
      }
      if ((e.key === 'e' || e.key === 'E') && !inInput) {
        EV.Canvas.setEditMode(!EV.Canvas.editMode);
        return;
      }
      if (e.key === 'T' && !inInput) {
        cycleTheme();
        return;
      }
      if (!inInput && ['1', '2', '3', '4', '5'].includes(e.key)) {
        const tpls = ['standard', 'minimal', 'pro', 'research', 'focus'];
        EV_Templates.applyTemplate(tpls[+e.key - 1]);
        return;
      }
      // Arrow navigation for picks
      if (!inInput && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
        const picks = EV.Store.get('picks') || [];
        const sel = EV.Store.get('selectedPick');
        if (!picks.length) return;
        const idx = picks.findIndex(p => p.ticker === sel?.ticker);
        const next = e.key === 'ArrowDown'
          ? picks[Math.min(idx + 1, picks.length - 1)]
          : picks[Math.max(idx - 1, 0)];
        if (next) EV.Store.set('selectedPick', next);
        e.preventDefault();
      }
    });

    // Theme buttons
    document.querySelectorAll('.theme-btn').forEach(btn => {
      btn.addEventListener('click', () => setTheme(btn.dataset.theme));
    });

    // Edit mode wiring
    document.getElementById('ev-edit-done')?.addEventListener('click', () =>
      EV.Canvas.setEditMode(false)
    );

    // Palette close
    document.getElementById('ev-palette-close')?.addEventListener('click', () => {
      document.getElementById('ev-module-palette').hidden = true;
    });

    // Search
    const searchEl = document.getElementById('ev-search');
    if (searchEl) {
      searchEl.addEventListener('keydown', e => {
        if (e.key === 'Escape') { searchEl.value = ''; searchEl.blur(); }
        if (e.key === 'Enter' && searchEl.value.trim()) {
          const t = searchEl.value.trim().toUpperCase();
          EV.Store.set('searchQuery', t);
          EV.Store.set('selectedTicker', t);
          const match = (EV.Store.get('picks') || []).find(p => p.ticker === t);
          EV.Store.set('selectedPick', match || { ticker: t });
          searchEl.blur();
        }
      });
    }
  }

  window.addEventListener('DOMContentLoaded', init);
  window.EV_App = { setTheme, cycleTheme };
})();
