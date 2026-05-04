(() => {
  const CSS_ID = 'ev-category-nav-css';
  const CSS = `
/* ── vertical mode ── */
.nav-group{padding:0 14px;margin-bottom:18px;}
.nav-lbl{font-size:9px;letter-spacing:1.8px;color:var(--text-faint);text-transform:uppercase;margin-bottom:8px;padding-left:4px;}
.nav-item{display:flex;align-items:center;justify-content:space-between;padding:7px 10px;border-radius:4px;cursor:pointer;color:var(--text-dim);font-size:12px;margin-bottom:2px;transition:background 0.1s,color 0.1s;border-left:2px solid transparent;user-select:none;}
.nav-item:hover{background:var(--panel-3);color:var(--text);}
.nav-item.active{background:var(--panel-3);color:var(--text);border-left:2px solid var(--accent);padding-left:8px;}
.nav-item .nav-left{display:flex;align-items:center;gap:6px;}
.nav-badge{font-size:10px;color:var(--text-faint);background:var(--chip-bg);padding:1px 7px;border-radius:8px;min-width:20px;text-align:center;}
.nav-item.active .nav-badge{color:var(--accent);}
.nav-dot-warn{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--warn,#ffc857);flex-shrink:0;}
.nav-divider{height:1px;background:var(--border-soft);margin:8px 14px 14px;}
/* ── horizontal pill mode ── */
.nav-h-bar{display:flex;align-items:center;height:100%;padding:0 10px;gap:2px;overflow-x:auto;overflow-y:hidden;scrollbar-width:none;}
.nav-h-bar::-webkit-scrollbar{display:none;}
.nav-pill{display:flex;align-items:center;gap:5px;padding:4px 10px;border-radius:4px;cursor:pointer;color:var(--text-dim);font-size:11px;white-space:nowrap;transition:background 0.1s,color 0.1s;border:1px solid transparent;font-family:var(--font-mono);letter-spacing:0.2px;user-select:none;}
.nav-pill:hover{background:var(--panel-3);color:var(--text);}
.nav-pill.active{background:var(--panel-3);color:var(--accent);border-color:rgba(94,227,161,0.2);}
.nav-pill-badge{font-size:9px;color:var(--text-faint);background:var(--chip-bg);padding:1px 5px;border-radius:8px;min-width:16px;text-align:center;}
.nav-pill.active .nav-pill-badge{color:var(--accent);}
.nav-h-sep{width:1px;height:16px;background:var(--border);margin:0 5px;flex-shrink:0;}
`;

  function injectCSS() {
    if (document.getElementById(CSS_ID)) return;
    const s = document.createElement('style');
    s.id = CSS_ID;
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  const CATEGORIES = [
    { id: 'today',  label: "Today's Picks", icon: '◆', dataKey: null },
    { id: 'matrix', label: 'Signal Matrix',  icon: '⬡', dataKey: null },
    { id: 'mine',   label: 'My List',        icon: '★', dataKey: null },
  ];

  function countBadge(categoryId, picks) {
    if (categoryId === 'today' && Array.isArray(picks)) return picks.length;
    return 0;
  }

  // ── vertical nav builder ──────────────────────────────────────────────
  function buildNavItem(cat, picks, activeId) {
    const count = countBadge(cat.id, picks);
    const isActive = cat.id === activeId;
    const hasDot = cat.warnDot && count > 0;
    return `
      <div class="nav-item${isActive ? ' active' : ''}" data-nav-id="${cat.id}">
        <span class="nav-left">
          ${hasDot ? '<span class="nav-dot-warn"></span>' : ''}
          ${cat.icon ? `<span>${cat.icon}</span>` : ''}
          <span>${cat.label}</span>
        </span>
        <span class="nav-badge" data-badge="${cat.id}">${count || ''}</span>
      </div>`;
  }

  function buildNav(picks, activeId) {
    let html = '<div style="padding-top:6px;"><div class="nav-group">';
    CATEGORIES.forEach(cat => { html += buildNavItem(cat, picks, activeId); });
    html += `</div>
      <div class="nav-divider"></div>
      <div class="nav-group">
        <div class="nav-lbl">CANVAS</div>
        <div class="nav-item" data-nav-id="edit-layout">
          <span class="nav-left"><span>⊞</span><span>Edit Layout</span></span>
        </div>
        <div class="nav-item" data-nav-id="settings">
          <span class="nav-left"><span>⚙</span><span>Settings</span></span>
        </div>
      </div>
    </div>`;
    return html;
  }

  // ── horizontal pill bar builder ───────────────────────────────────────
  function buildHorizontal(picks, activeId) {
    let html = '<div class="nav-h-bar">';
    CATEGORIES.forEach(cat => {
      const isActive = cat.id === activeId;
      const count = countBadge(cat.id, picks);
      const icon = cat.icon ? `<span>${cat.icon}</span>` : '';
      const badge = count ? `<span class="nav-pill-badge">${count}</span>` : '';
      html += `<div class="nav-pill${isActive ? ' active' : ''}" data-nav-id="${cat.id}">${icon}<span>${cat.label}</span>${badge}</div>`;
    });
    html += '</div>';
    return html;
  }

  class CategoryNavModule extends (window.EV ? window.EV.Module : class { constructor(el,cfg){this.el=el;this.config=cfg;this._unsubs=[];} mount(){} unmount(){this._unsubs.forEach(f=>f());this._unsubs=[];} _sub(k,f){if(window.EV)this._unsubs.push(window.EV.Store.subscribe(k,f));} }) {
    mount() {
      injectCSS();
      this._activeId = 'today';
      const picks = (window.EV && window.EV.Store.get('picks')) || [];
      this._render(picks);

      this._sub('picks', picks => {
        if (this.config.horizontal) this._render(picks);
        else this._updateBadges(picks);
      });
      this._sub('activeCategory', id => { if (id) this._setActive(id); });
    }

    _render(picks) {
      if (this.config.horizontal) {
        this.el.innerHTML = buildHorizontal(picks, this._activeId);
      } else {
        this.el.innerHTML = buildNav(picks, this._activeId);
      }
      this._bindClicks();
    }

    _bindClicks() {
      this.el.querySelectorAll('[data-nav-id]').forEach(el => {
        el.addEventListener('click', () => {
          const id = el.dataset.navId;
          if (id === 'edit-layout') {
            if (window.EV && window.EV.Canvas) window.EV.Canvas.setEditMode(true);
            return;
          }
          if (id === 'settings') return;
          this._setActive(id);
          if (window.EV) window.EV.Store.set('activeCategory', id);
        });
      });
    }

    _setActive(id) {
      this._activeId = id;
      this.el.querySelectorAll('.nav-item, .nav-pill').forEach(el => {
        el.classList.toggle('active', el.dataset.navId === id);
      });
    }

    _updateBadges(picks) {
      CATEGORIES.forEach(cat => {
        const el = this.el.querySelector(`[data-badge="${cat.id}"]`);
        if (el) el.textContent = countBadge(cat.id, picks) || '';
      });
    }
  }

  CategoryNavModule.id = 'category-nav';
  CategoryNavModule.label = 'Category Nav';
  CategoryNavModule.defaultSize = 'M';
  CategoryNavModule.supportedSizes = ['M'];

  if (window.EV && window.EV.registry) {
    window.EV.registry.register(CategoryNavModule);
  }
  window.CategoryNavModule = CategoryNavModule;
})();
