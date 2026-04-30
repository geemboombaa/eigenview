(function () {
  'use strict';

  const THEMES = ['dark', 'light', 'glass', 'bento'];
  let themeIdx = 0;

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

    // Mount nav
    const navSlot = document.getElementById('ev-nav-slot');
    if (navSlot) EV.Canvas.mountModule('category-nav', navSlot, { slot: 'nav' });

    // Mount chat
    const chatSlot = document.getElementById('ev-chat-slot');
    if (chatSlot) EV.Canvas.mountModule('ai-chat', chatSlot, { slot: 'chat' });

    // Mount main canvas modules
    const canvas = document.getElementById('ev-canvas');
    function addMod(id) {
      const el = document.createElement('div');
      canvas.appendChild(el);
      EV.Canvas.mountModule(id, el);
    }
    addMod('market-context');
    addMod('pick-cards');
    addMod('price-chart');
    addMod('factor-strip');

    // Fetch data in parallel
    const [regime, picks] = await Promise.all([
      EV.API.get('/api/market/regime'),
      EV.API.get('/api/picks')
    ]);

    if (regime) EV.Store.set('regime', regime);

    if (picks && Array.isArray(picks) && picks.length > 0) {
      EV.Store.set('picks', picks);
      EV.Store.set('selectedPick', picks[0]);
      const badge = document.getElementById('ev-scan-time');
      if (badge) {
        badge.textContent = `✓ ${picks.length} pick${picks.length !== 1 ? 's' : ''}`;
        badge.style.color = 'var(--accent)';
      }
    } else {
      const badge = document.getElementById('ev-scan-time');
      if (badge) badge.textContent = 'No picks today';
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
        document.querySelector('.chat-input')?.focus();
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
          EV.Store.set('searchQuery', searchEl.value.trim().toUpperCase());
          searchEl.blur();
        }
      });
    }
  }

  window.addEventListener('DOMContentLoaded', init);
  window.EV_App = { setTheme, cycleTheme };
})();
