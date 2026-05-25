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
      chat: true,
      showPicks: true,
      showMain: true
    },
    {
      id: 'minimal',
      name: 'MINIMAL',
      key: '2',
      description: 'Picks only + chat (no detail)',
      mainModules: ['pick-cards'],
      nav: false,
      chat: true,
      showPicks: true,
      showMain: false
    },
    {
      id: 'pro',
      name: 'PRO',
      key: '3',
      description: 'Dense table + chart + compact nav',
      mainModules: ['market-context', 'pick-cards', 'price-chart'],
      nav: true,
      chat: true,
      showPicks: true,
      showMain: true,
      showStrip: false
    },
    {
      id: 'research',
      name: 'RESEARCH',
      key: '4',
      description: 'Dormant bets + history + deep chat',
      mainModules: ['market-context', 'pick-cards', 'factor-strip'],
      nav: true,
      chat: true,
      showPicks: true,
      showMain: true
    },
    {
      id: 'focus',
      name: 'FOCUS',
      key: '5',
      description: 'Single pick full-screen',
      mainModules: ['price-chart', 'factor-strip'],
      nav: false,
      chat: true,
      showPicks: false,
      showMain: true
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

    const showPicks = tpl.showPicks !== false;
    const showMain  = tpl.showMain  !== false;

    const mainCol   = document.getElementById('ev-main-col');
    const picksSlot = document.getElementById('ev-picks-slot');
    const nav       = document.getElementById('ev-nav-slot');
    const stripSlot = document.getElementById('ev-strip-slot');
    const body      = document.getElementById('ev-body');

    if (mainCol)   mainCol.style.display   = showMain  ? '' : 'none';
    if (picksSlot) picksSlot.style.display = showPicks ? '' : 'none';
    if (nav)       nav.style.display       = tpl.nav   ? '' : 'none';
    if (stripSlot) stripSlot.style.display = tpl.showStrip !== false ? '' : 'none';

    if (body) {
      const pc = showPicks ? '380px' : '0';
      const mc = showMain  ? '1fr'   : '0';
      body.style.gridTemplateColumns = `${pc} ${mc} 340px`;
    }

    EV.Store.set('activeTemplate', id);
    EV.Store.set('templateDef', tpl);
  }

  function init() {
    renderSwitcher();
    applyTemplate('standard');
  }

  window.EV_Templates = { TEMPLATES, applyTemplate, init };
})();
