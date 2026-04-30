(() => {
  const CSS_ID = 'ev-category-nav-css';
  const CSS = `
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
.nav-bottom{position:absolute;bottom:0;left:0;right:0;border-top:1px solid var(--border);padding:8px 0 6px;}
`;

  function injectCSS() {
    if (document.getElementById(CSS_ID)) return;
    const s = document.createElement('style');
    s.id = CSS_ID;
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  const CATEGORIES = [
    { id: 'today',     label: "Today's Picks",   icon: '◆', section: 'TODAY',      dataKey: null },
    { id: 'dormant',   label: 'Dormant Firing',   icon: '◈', section: 'TODAY',      dataKey: 'dormant', warnDot: true },
    { id: 'bench',     label: 'Signal Bench',     icon: '',  section: 'TODAY',      dataKey: null },
    { id: 'breakout',  label: 'Breakouts',        icon: '',  section: 'CATEGORIES', dataKey: 'breakout' },
    { id: 'pullback',  label: 'Pullbacks',        icon: '',  section: 'CATEGORIES', dataKey: 'pullback' },
    { id: 'compression', label: 'Compression',   icon: '',  section: 'CATEGORIES', dataKey: 'compression' },
    { id: 'earnings',  label: 'Earnings Plays',   icon: '',  section: 'CATEGORIES', dataKey: 'earnings' },
    { id: 'mylist',    label: '⭐ My List',        icon: '',  section: 'WORKFLOW',   dataKey: null },
    { id: 'closed',    label: 'Closed Picks',     icon: '',  section: 'WORKFLOW',   dataKey: null },
    { id: 'alerts',    label: '⟁ Alerts',         icon: '',  section: 'WORKFLOW',   dataKey: null },
  ];

  function countBadge(categoryId, picks) {
    if (!Array.isArray(picks)) return 0;
    switch (categoryId) {
      case 'today':       return picks.length;
      case 'dormant':     return picks.filter(p => p.factors?.dormant?.firing).length;
      case 'breakout':    return picks.filter(p => p.setup_type === 'breakout').length;
      case 'pullback':    return picks.filter(p => p.setup_type === 'pullback').length;
      case 'compression': return picks.filter(p => p.setup_type === 'compression').length;
      case 'earnings':    return picks.filter(p => p.factors?.sentiment?.detail?.catalyst_near).length;
      default:            return 0;
    }
  }

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
        <span class="nav-badge" data-badge="${cat.id}">${count}</span>
      </div>`;
  }

  function buildNav(picks, activeId) {
    const sections = ['TODAY', 'CATEGORIES', 'WORKFLOW'];
    let html = '<div style="padding-top:6px;">';
    sections.forEach(sec => {
      const items = CATEGORIES.filter(c => c.section === sec);
      if (!items.length) return;
      html += `<div class="nav-group"><div class="nav-lbl">${sec}</div>`;
      items.forEach(cat => { html += buildNavItem(cat, picks, activeId); });
      html += '</div>';
    });
    html += `
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

  class CategoryNavModule extends (window.EV ? window.EV.Module : class { constructor(el,cfg){this.el=el;this.config=cfg;this._unsubs=[];} mount(){} unmount(){this._unsubs.forEach(f=>f());this._unsubs=[];} _sub(k,f){if(window.EV)this._unsubs.push(window.EV.Store.subscribe(k,f));} }) {
    mount() {
      injectCSS();
      this._activeId = 'today';
      const picks = (window.EV && window.EV.Store.get('picks')) || [];
      this._render(picks);

      this._sub('picks', (picks) => this._updateBadges(picks));
      this._sub('activeCategory', (id) => {
        if (id) this._setActive(id);
      });
    }

    _render(picks) {
      this.el.innerHTML = buildNav(picks, this._activeId);
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
          if (id === 'settings') return; // future
          this._setActive(id);
          if (window.EV) window.EV.Store.set('activeCategory', id);
        });
      });
    }

    _setActive(id) {
      this._activeId = id;
      this.el.querySelectorAll('.nav-item').forEach(el => {
        el.classList.toggle('active', el.dataset.navId === id);
      });
    }

    _updateBadges(picks) {
      CATEGORIES.forEach(cat => {
        const el = this.el.querySelector(`[data-badge="${cat.id}"]`);
        if (el) el.textContent = countBadge(cat.id, picks);
      });
      // show/hide dormant dot
      const dormantItem = this.el.querySelector('[data-nav-id="dormant"] .nav-left');
      if (dormantItem) {
        const count = countBadge('dormant', picks);
        const existing = dormantItem.querySelector('.nav-dot-warn');
        if (count > 0 && !existing) {
          dormantItem.insertAdjacentHTML('afterbegin', '<span class="nav-dot-warn"></span>');
        } else if (count === 0 && existing) {
          existing.remove();
        }
      }
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
