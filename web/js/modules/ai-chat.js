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
<style id="ev-ai-chat-style">
.ev-chat { display:flex; flex-direction:column; height:100%; background:var(--bg-primary,#13131f); border-radius:12px; overflow:hidden; }
.ev-chat-header { display:flex; align-items:center; justify-content:space-between; padding:10px 14px; border-bottom:1px solid var(--border,#2a2a3e); flex-shrink:0; }
.ev-chat-title { font-size:13px; font-weight:600; color:var(--text-primary,#e2e2f0); }
.ev-chat-clear { background:none; border:1px solid var(--border,#2a2a3e); color:var(--text-muted,#888); font-size:11px; padding:4px 8px; border-radius:6px; cursor:pointer; transition:all 0.15s; }
.ev-chat-clear:hover { border-color:var(--accent,#7c6af5); color:var(--accent,#7c6af5); }
.ev-chat-messages { flex:1; overflow-y:auto; padding:12px; display:flex; flex-direction:column; gap:10px; }
.ev-chat-messages::-webkit-scrollbar { width:4px; }
.ev-chat-messages::-webkit-scrollbar-track { background:transparent; }
.ev-chat-messages::-webkit-scrollbar-thumb { background:var(--border,#2a2a3e); border-radius:2px; }
.ev-msg { max-width:85%; line-height:1.5; font-size:13px; }
.ev-msg-user { align-self:flex-end; background:var(--accent,#7c6af5); color:#fff; padding:8px 12px; border-radius:14px 14px 4px 14px; }
.ev-msg-ai { align-self:flex-start; background:var(--bg-secondary,#1e1e2e); color:var(--text-primary,#e2e2f0); padding:8px 12px; border-radius:4px 14px 14px 14px; border:1px solid var(--border,#2a2a3e); }
.ev-msg-ai code { background:var(--bg-primary,#13131f); padding:1px 4px; border-radius:4px; font-size:12px; font-family:monospace; }
.ev-msg-ai strong { font-weight:600; color:var(--text-primary,#e2e2f0); }
.ev-chat-suggestions { display:flex; gap:6px; padding:8px 12px; flex-wrap:wrap; flex-shrink:0; border-top:1px solid var(--border,#2a2a3e); }
.ev-chip { background:var(--bg-secondary,#1e1e2e); border:1px solid var(--border,#2a2a3e); color:var(--text-secondary,#aaa); font-size:11px; padding:4px 10px; border-radius:20px; cursor:pointer; transition:all 0.15s; white-space:nowrap; }
.ev-chip:hover { border-color:var(--accent,#7c6af5); color:var(--accent,#7c6af5); background:color-mix(in srgb,var(--accent,#7c6af5) 10%,transparent); }
.ev-chat-input-row { display:flex; gap:8px; padding:10px 12px; border-top:1px solid var(--border,#2a2a3e); flex-shrink:0; align-items:flex-end; }
.ev-chat-textarea { flex:1; background:var(--bg-secondary,#1e1e2e); border:1px solid var(--border,#2a2a3e); color:var(--text-primary,#e2e2f0); font-size:13px; padding:8px 10px; border-radius:8px; resize:none; min-height:36px; max-height:120px; font-family:inherit; outline:none; transition:border-color 0.15s; line-height:1.4; }
.ev-chat-textarea:focus { border-color:var(--accent,#7c6af5); }
.ev-chat-textarea::placeholder { color:var(--text-muted,#888); }
.ev-chat-send { background:var(--accent,#7c6af5); border:none; color:#fff; width:34px; height:34px; border-radius:8px; cursor:pointer; display:flex; align-items:center; justify-content:center; flex-shrink:0; transition:opacity 0.15s, transform 0.1s; }
.ev-chat-send:hover:not(:disabled) { opacity:0.85; transform:scale(1.05); }
.ev-chat-send:disabled { opacity:0.4; cursor:not-allowed; }
.ev-chat-send svg { width:16px; height:16px; }
.ev-spinner { width:14px; height:14px; border:2px solid rgba(255,255,255,0.3); border-top-color:#fff; border-radius:50%; animation:evSpin 0.7s linear infinite; }
@keyframes evSpin { to { transform:rotate(360deg); } }
</style>`;

  const DEFAULT_PROMPTS = [
    "What's the market regime today?",
    "Which pick has highest conviction?",
    "Explain dormant-bet radar",
  ];

  function tickerPrompts(ticker) {
    return [
      "Explain this setup",
      "What's the risk?",
      "Why did TA fire?",
      `Explain GEX for ${ticker}`,
      "What structure do you recommend?",
    ];
  }

  function renderMd(text) {
    return text
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>');
  }

  class AiChatModule extends Base {
    static id = 'ai-chat';

    constructor(el, config) {
      super(el, config);
      this._messages = [];
      this._streaming = false;
    }

    mount() {
      if (!document.getElementById('ev-ai-chat-style')) {
        document.head.insertAdjacentHTML('beforeend', STYLE);
      }
      this._buildShell();
      this._addWelcome();
      this._renderSuggestions(null);
      this._bindEvents();

      this._sub('selectedPick', pick => this._renderSuggestions(pick));
      this._sub('chatPrefill', text => {
        if (!text) return;
        const ta = this._qs('.ev-chat-textarea');
        if (ta) { ta.value = text; ta.focus(); ta.style.height = 'auto'; ta.style.height = ta.scrollHeight + 'px'; }
      });
    }

    _buildShell() {
      this._html(`
<div class="ev-chat">
  <div class="ev-chat-header">
    <span class="ev-chat-title">AI Assistant</span>
    <button class="ev-chat-clear">Clear</button>
  </div>
  <div class="ev-chat-messages"></div>
  <div class="ev-chat-suggestions"></div>
  <div class="ev-chat-input-row">
    <textarea class="ev-chat-textarea" placeholder="Ask about any pick, factor, or market condition…" rows="1"></textarea>
    <button class="ev-chat-send" title="Send">
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <line x1="14" y1="2" x2="2" y2="8"/><line x1="14" y1="2" x2="8" y2="14"/><line x1="2" y1="8" x2="8" y2="14"/>
      </svg>
    </button>
  </div>
</div>`);
    }

    _addWelcome() {
      this._appendAI("Hi! I'm your trading assistant. Ask me about any pick, factor, or market condition.");
    }

    _appendUser(text) {
      const div = document.createElement('div');
      div.className = 'ev-msg ev-msg-user';
      div.textContent = text;
      this._qs('.ev-chat-messages').appendChild(div);
      this._scrollBottom();
    }

    _appendAI(text) {
      const div = document.createElement('div');
      div.className = 'ev-msg ev-msg-ai';
      div.innerHTML = renderMd(text);
      this._qs('.ev-chat-messages').appendChild(div);
      this._scrollBottom();
      return div;
    }

    _scrollBottom() {
      const msgs = this._qs('.ev-chat-messages');
      if (msgs) msgs.scrollTop = msgs.scrollHeight;
    }

    _renderSuggestions(pick) {
      const container = this._qs('.ev-chat-suggestions');
      if (!container) return;
      const prompts = pick?.ticker ? tickerPrompts(pick.ticker) : DEFAULT_PROMPTS;
      container.innerHTML = prompts.map(p =>
        `<button class="ev-chip" data-prompt="${p.replace(/"/g, '&quot;')}">${p}</button>`
      ).join('');
      container.querySelectorAll('.ev-chip').forEach(chip => {
        chip.addEventListener('click', () => this._sendMessage(chip.dataset.prompt));
      });
    }

    _bindEvents() {
      const btn = this._qs('.ev-chat-send');
      const ta = this._qs('.ev-chat-textarea');
      const clear = this._qs('.ev-chat-clear');

      btn?.addEventListener('click', () => this._sendFromInput());

      ta?.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this._sendFromInput(); }
      });

      ta?.addEventListener('input', () => {
        ta.style.height = 'auto';
        ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
      });

      clear?.addEventListener('click', () => {
        const msgs = this._qs('.ev-chat-messages');
        if (msgs) msgs.innerHTML = '';
        this._addWelcome();
      });
    }

    _sendFromInput() {
      const ta = this._qs('.ev-chat-textarea');
      if (!ta) return;
      const text = ta.value.trim();
      if (!text || this._streaming) return;
      ta.value = '';
      ta.style.height = 'auto';
      this._sendMessage(text);
    }

    _sendMessage(text) {
      if (!text || this._streaming) return;
      this._appendUser(text);
      const ticker = window.EV?.Store?.get('selectedTicker') ?? null;
      this._streaming = true;
      const sendBtn = this._qs('.ev-chat-send');
      const ta = this._qs('.ev-chat-textarea');
      if (sendBtn) sendBtn.innerHTML = '<div class="ev-spinner"></div>';
      if (sendBtn) sendBtn.disabled = true;
      if (ta) ta.disabled = true;

      const aiDiv = this._appendAI('');
      let buffer = '';

      const api = window.EV?.API;
      if (!api) {
        aiDiv.innerHTML = renderMd('_(API not available)_');
        this._done(sendBtn, ta);
        return;
      }

      api.streamChat(
        text,
        ticker,
        token => {
          buffer += token;
          aiDiv.innerHTML = renderMd(buffer);
          this._scrollBottom();
        },
        () => {
          if (!buffer) aiDiv.innerHTML = renderMd('_(No response)_');
          this._done(sendBtn, ta);
        }
      );
    }

    _done(sendBtn, ta) {
      this._streaming = false;
      if (sendBtn) {
        sendBtn.innerHTML = `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="14" y1="2" x2="2" y2="8"/><line x1="14" y1="2" x2="8" y2="14"/><line x1="2" y1="8" x2="8" y2="14"/></svg>`;
        sendBtn.disabled = false;
      }
      if (ta) { ta.disabled = false; ta.focus(); }
      this._scrollBottom();
    }
  }

  if (window.EV?.registry) {
    EV.registry.register(AiChatModule);
  } else {
    window.__EV_PENDING_MODULES = window.__EV_PENDING_MODULES || [];
    window.__EV_PENDING_MODULES.push(AiChatModule);
  }
})();
