(() => {
  const Base = window.EV?.Module ?? class {
    constructor(el, config) { this.el = el; this.config = config || {}; this._subs = []; }
    mount() {}
    unmount() { this._subs.forEach(u => u()); this._subs = []; }
    resize() {}
    _sub(key, fn) {
      if (window.EV?.Store) { this._subs.push(window.EV.Store.subscribe(key, fn)); }
    }
    _html(h) { this.el.innerHTML = h; }
    _qs(sel) { return this.el.querySelector(sel); }
    _qsa(sel) { return this.el.querySelectorAll(sel); }
  };

  const STYLE = `
<style id="ev-voice-orb-style">
.ev-orb-wrap { display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; gap:12px; padding:16px; }
.orb-container { position:relative; display:flex; align-items:center; justify-content:center; width:80px; height:80px; }
.orb-waves { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; pointer-events:none; }
.orb-waves div {
  position:absolute; width:64px; height:64px; border-radius:50%;
  border:2px solid var(--accent,#7c6af5); opacity:0;
}
.orb-container.listening .orb-waves div:nth-child(1) { animation:evOrbWave 1.5s ease-out infinite 0s; }
.orb-container.listening .orb-waves div:nth-child(2) { animation:evOrbWave 1.5s ease-out infinite 0.2s; }
.orb-container.listening .orb-waves div:nth-child(3) { animation:evOrbWave 1.5s ease-out infinite 0.4s; }
@keyframes evOrbWave {
  0%   { transform:scale(1); opacity:0.6; }
  100% { transform:scale(2.5); opacity:0; }
}
.orb-btn {
  position:relative; z-index:1;
  width:64px; height:64px; border-radius:50%;
  background:var(--accent,#7c6af5);
  border:none; cursor:pointer; color:#fff;
  display:flex; align-items:center; justify-content:center;
  box-shadow:0 0 20px color-mix(in srgb,var(--accent,#7c6af5) 40%,transparent);
  transition:transform 0.15s, box-shadow 0.15s, opacity 0.15s;
}
.orb-btn:hover:not(:disabled) { transform:scale(1.08); box-shadow:0 0 32px color-mix(in srgb,var(--accent,#7c6af5) 60%,transparent); }
.orb-btn:disabled { opacity:0.35; cursor:not-allowed; }
.orb-btn svg { width:24px; height:24px; }
.orb-container.listening .orb-btn { box-shadow:0 0 32px color-mix(in srgb,var(--accent,#7c6af5) 70%,transparent); }
.orb-status { font-size:12px; color:var(--text-muted,#888); text-align:center; min-height:18px; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.orb-container.listening + .orb-status { color:var(--accent,#7c6af5); }
</style>`;

  const MIC_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <rect x="9" y="2" width="6" height="12" rx="3"/>
  <path d="M5 10a7 7 0 0 0 14 0"/>
  <line x1="12" y1="19" x2="12" y2="22"/>
  <line x1="8" y1="22" x2="16" y2="22"/>
</svg>`;

  class VoiceOrbModule extends Base {
    static id = 'voice-orb';

    constructor(el, config) {
      super(el, config);
      this._recognition = null;
      this._listening = false;
    }

    mount() {
      if (!document.getElementById('ev-voice-orb-style')) {
        document.head.insertAdjacentHTML('beforeend', STYLE);
      }

      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

      this._html(`
<div class="ev-orb-wrap">
  <div class="orb-container">
    <div class="orb-waves" aria-hidden="true"><div></div><div></div><div></div></div>
    <button class="orb-btn" aria-label="Voice input" ${SR ? '' : 'disabled'}>${MIC_ICON}</button>
  </div>
  <div class="orb-status">${SR ? 'Click to speak' : 'Voice not supported in this browser'}</div>
</div>`);

      if (!SR) return;

      const recognition = new SR();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = 'en-US';
      this._recognition = recognition;

      const container = this._qs('.orb-container');
      const status = this._qs('.orb-status');
      const btn = this._qs('.orb-btn');

      recognition.onstart = () => {
        this._listening = true;
        container.classList.add('listening');
        status.textContent = 'Listening…';
      };

      recognition.onresult = e => {
        let interim = '';
        let final = '';
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const t = e.results[i][0].transcript;
          if (e.results[i].isFinal) final += t;
          else interim += t;
        }
        status.textContent = final || interim || 'Listening…';
        if (final) {
          if (window.EV?.Store) EV.Store.set('chatPrefill', final.trim());
          recognition.stop();
        }
      };

      recognition.onerror = e => {
        status.textContent = e.error === 'no-speech' ? 'No speech detected' : `Error: ${e.error}`;
        this._stopListening(container);
      };

      recognition.onend = () => {
        this._stopListening(container);
        if (status.textContent === 'Listening…') status.textContent = 'Click to speak';
      };

      btn.addEventListener('click', () => {
        if (this._listening) {
          recognition.stop();
        } else {
          try { recognition.start(); }
          catch (e) { status.textContent = 'Click to speak'; }
        }
      });
    }

    _stopListening(container) {
      this._listening = false;
      container?.classList.remove('listening');
    }

    unmount() {
      if (this._recognition && this._listening) {
        try { this._recognition.stop(); } catch (_) {}
      }
      super.unmount();
    }
  }

  if (window.EV?.registry) {
    EV.registry.register(VoiceOrbModule);
  } else {
    window.__EV_PENDING_MODULES = window.__EV_PENDING_MODULES || [];
    window.__EV_PENDING_MODULES.push(VoiceOrbModule);
  }
})();
