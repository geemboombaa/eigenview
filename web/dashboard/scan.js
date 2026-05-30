/* EigenView dashboard — SCAN trigger + status polling + progress bar.
   Async. Never auto-triggers; only on user click. Reflects an in-flight scan on load.
   The engine reports a text status + running flag (no %) → indeterminate bar + live text. */

window.EV_SCAN = (() => {
  let btn, bar, txt, fill, dlCheck, onDone, onTick;
  let pollTimer = null;
  let wasRunning = false;

  function startPoll() { if (!pollTimer) pollTimer = setInterval(poll, 2000); }
  function stopPoll()  { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } }

  function render(s) {
    const running = !!(s && s.running);
    if (running) {
      bar.classList.add('on'); bar.classList.remove('err');
      btn.disabled = true; btn.textContent = '⟳ SCANNING…';
      const total = s.total || 0, done = s.done || 0;
      // Real % during scoring/thesis (counts available); indeterminate during download/rank.
      const determinate = total > 0 && (s.phase === 'score' || s.phase === 'thesis');
      if (determinate) {
        fill.classList.remove('working');
        fill.style.width = Math.max(2, Math.round(done / total * 100)) + '%';
      } else {
        fill.classList.add('working');
        fill.style.width = '';
      }
      txt.textContent = s.message || 'Scanning…';
    } else {
      fill.classList.remove('working'); fill.style.width = '0%';
      btn.disabled = false; btn.textContent = '⟳ SCAN';
      if (s && s.error) {
        bar.classList.add('on'); bar.classList.add('err');
        txt.textContent = 'Scan failed: ' + s.error;
      } else if (s && s.message && s.message !== 'idle') {
        bar.classList.add('on'); bar.classList.remove('err');
        txt.textContent = s.message;
      } else {
        bar.classList.remove('on');
        txt.textContent = '';
      }
    }
  }

  async function poll() {
    let s;
    try { s = await EV_DATA.scanStatus(); }
    catch { return; }
    render(s);
    if (s.running) {
      wasRunning = true;
      if (onTick) onTick();          // live-populate completed tickers during the scan
    } else {
      stopPoll();
      if (wasRunning) { wasRunning = false; if (onDone) onDone(); }
    }
  }

  async function trigger() {
    const dl = !!(dlCheck && dlCheck.checked);
    btn.disabled = true;
    bar.classList.add('on'); bar.classList.remove('err');
    txt.textContent = dl ? 'Starting scan + fresh download…' : 'Starting scan…';
    let r;
    try { r = await EV_DATA.triggerScan(dl); }
    catch (e) { render({ running: false, error: e.message }); return; }

    if (r.status === 'too_recent' || r.status === 'already_running') {
      // Surface the engine's own message verbatim — honest, no hiding the cooldown.
      render({ running: r.status === 'already_running', message: r.message || r.status });
      if (r.status === 'already_running') { wasRunning = true; startPoll(); }
      else { btn.disabled = false; btn.textContent = '⟳ SCAN'; }
      return;
    }
    // status === 'started'
    wasRunning = true;
    fill.classList.add('working');
    startPoll();
    poll();
  }

  function mount(opts) {
    btn = opts.button; bar = opts.bar; txt = opts.text; fill = opts.fill;
    dlCheck = opts.download; onDone = opts.onComplete; onTick = opts.onProgress;
    btn.addEventListener('click', trigger);
    // Reflect an already-running scan if the page is opened mid-scan.
    poll();
  }

  return { mount };
})();
