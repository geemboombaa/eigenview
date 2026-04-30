(function () {
  'use strict';

  const TEMPLATES = [
    {
      id: 'standard',
      name: 'STANDARD',
      key: '1',
      description: 'Context + picks + detail + chat',
      mainModules: ['market-context', 'pick-cards', 'price-chart', 'factor-strip'],
      nav: true,
      chat: true
    },
    {
      id: 'minimal',
      name: 'MINIMAL',
      key: '2',
      description: 'Picks only + chat (no detail)',
      mainModules: ['pick-cards'],
      nav: false,
      chat: true
    },
    {
      id: 'pro',
      name: 'PRO',
      key: '3',
      description: 'Dense table + chart + compact nav',
      mainModules: ['market-context', 'pick-cards', 'price-chart'],
      nav: true,
      chat: true
    },
    {
      id: 'research',
      name: 'RESEARCH',
      key: '4',
      description: 'Dormant bets + history + deep chat',
      mainModules: ['market-context', 'pick-cards', 'factor-strip'],
      nav: true,
      chat: true
    },
    {
      id: 'focus',
      name: 'FOCUS',
      key: '5',
      description: 'Single pick full-screen',
      mainModules: ['price-chart', 'factor-strip'],
      nav: false,
      chat: true
    }
  ];

  function renderSwitcher() {
    const sw = document.getElementById('ev-tpl-switcher');
    if (!sw) return;
    sw.innerHTML = TEMPLATES.map(t =>
      `<button class="tpl-btn" data-tpl="${t.id}" title="${t.description}">${t.name}</button>`
    ).join('');
    sw.querySelectorAll('.tpl-btn').forEach(btn => {
      btn.addEventListener('click', () => applyTemplate(btn.dataset.tpl));
    });
  }

  function applyTemplate(id) {
    const tpl = TEMPLATES.find(t => t.id === id);
    if (!tpl) return;
    document.querySelectorAll('.tpl-btn').forEach(b =>
      b.classList.toggle('active', b.dataset.tpl === id)
    );
    // Body grid: hide nav if !tpl.nav
    const body = document.getElementById('ev-body');
    if (body) {
      if (tpl.nav) {
        body.style.gridTemplateColumns = '220px 1fr 340px';
      } else {
        body.style.gridTemplateColumns = '0 1fr 340px';
      }
    }
    const nav = document.getElementById('ev-nav-slot');
    if (nav) nav.style.display = tpl.nav ? '' : 'none';

    EV.Store.set('activeTemplate', id);
    EV.Store.set('templateDef', tpl);
  }

  function init() {
    renderSwitcher();
    applyTemplate('standard');
  }

  window.EV_Templates = { TEMPLATES, applyTemplate, init };
})();
