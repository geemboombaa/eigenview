/* EigenEdge — GLAM behavior layer. Additive, framework-free, observer-driven.
   Touches NOTHING in table.js — watches the DOM and layers polish on top.
   Full revert: remove the glam.css <link> + this <script> from index.html.
   Each hook maps to a numbered effect in glam.css (GLAM-1 / GLAM-5 / GLAM-6). */
(() => {
  // ── GLAM-1 · regime aurora: mirror Gate-0 regime onto a body class ──
  function setRegime() {
    try {
      const el = document.getElementById('regimeBar');
      if (!el) return;
      const t = el.textContent || '';
      const cls = t.includes('GREEN') ? 'regime-g'
                : t.includes('YELLOW') ? 'regime-a'
                : t.includes('RED') ? 'regime-r' : '';
      document.body.classList.remove('regime-g', 'regime-a', 'regime-r');
      if (cls) document.body.classList.add(cls);
    } catch {}
  }

  // ── GLAM-5/6 · diff table rows between renders: flash arrivals, pulse changed numbers ──
  let prev = new Map();   // ticker -> { price }
  function diffTable() {
    try {
      const rows = document.querySelectorAll('#tableHost tr[data-tk]');
      const next = new Map();
      rows.forEach(tr => {
        const tk = tr.getAttribute('data-tk');
        if (!tk) return;
        const priceEl = tr.querySelector('.col-spot .price, .col-price .price, td .price');
        const price = priceEl ? priceEl.textContent.trim() : '';
        next.set(tk, { price });
        const before = prev.get(tk);
        if (!before) {
          // GLAM-5: new ticker this render → arrival flash
          tr.classList.remove('glam-new'); void tr.offsetWidth; tr.classList.add('glam-new');
        } else if (before.price !== price && priceEl) {
          // GLAM-6: price changed → number pulse
          priceEl.classList.remove('glam-upd'); void priceEl.offsetWidth; priceEl.classList.add('glam-upd');
        }
      });
      prev = next;
    } catch {}
  }

  function onMutate() { setRegime(); diffTable(); }

  function start() {
    setRegime(); diffTable();
    const obs = new MutationObserver(() => onMutate());
    const host = document.getElementById('tableHost');
    const reg = document.getElementById('regimeBar');
    if (host) obs.observe(host, { childList: true, subtree: true });
    if (reg) obs.observe(reg, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
