(function () {
  'use strict';

  // ===== STORE =====
  const Store = (() => {
    const state = {};
    const subs = {};
    return {
      set(key, val) {
        state[key] = val;
        (subs[key] || []).forEach(fn => fn(val));
      },
      get(key) { return state[key]; },
      subscribe(key, fn) {
        (subs[key] || (subs[key] = [])).push(fn);
        return () => { subs[key] = (subs[key] || []).filter(f => f !== fn); };
      }
    };
  })();

  // ===== API CLIENT =====
  const API = {
    base: '',
    async get(path) {
      try {
        const r = await fetch(this.base + path);
        if (!r.ok) return null;
        return await r.json();
      } catch (e) {
        console.warn('EV API GET', path, e);
        return null;
      }
    },
    async post(path, body) {
      try {
        const r = await fetch(this.base + path, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        if (!r.ok) return null;
        return await r.json();
      } catch (e) {
        console.warn('EV API POST', path, e);
        return null;
      }
    },
    streamChat(question, ticker, onToken, onDone) {
      const ctrl = new AbortController();
      fetch(this.base + '/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          ticker,
          context: Store.get('selectedPick') || {}
        }),
        signal: ctrl.signal
      }).then(async r => {
        const reader = r.body.getReader();
        const dec = new TextDecoder();
        let buf = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += dec.decode(value, { stream: true });
          const parts = buf.split('\n\n');
          buf = parts.pop();
          for (const part of parts) {
            const line = part.trim();
            if (!line.startsWith('data: ')) continue;
            const raw = line.slice(6);
            if (raw === '[DONE]') { onDone && onDone(); return; }
            let token = raw;
            try { token = JSON.parse(raw); } catch {}
            onToken(token);
          }
        }
        onDone && onDone();
      }).catch(e => {
        if (e.name !== 'AbortError') console.warn('EV stream error', e);
        onDone && onDone();
      });
      return ctrl;
    }
  };

  // ===== MODULE BASE CLASS =====
  class Module {
    static id = 'base';
    static label = 'Module';
    static defaultSize = 'M';
    static supportedSizes = ['M', 'L'];

    constructor(el, config = {}) {
      this.el = el;
      this.config = config;
      this._unsubs = [];
      this._size = config.size || this.constructor.defaultSize;
    }

    mount() {}
    unmount() { this._unsubs.forEach(fn => fn()); this._unsubs = []; }
    resize(size) { this._size = size; }

    _sub(key, fn) { this._unsubs.push(Store.subscribe(key, fn)); }
    _html(h) { this.el.innerHTML = h; }
    _qs(sel) { return this.el.querySelector(sel); }
    _qsa(sel) { return Array.from(this.el.querySelectorAll(sel)); }

    static chrome(id, label, innerHtml) {
      return `
        <div class="ev-module-bar">
          <span class="ev-drag-handle"><span></span><span></span><span></span></span>
          <span class="ev-module-label">${label}</span>
          <button class="ev-module-close" data-close="${id}" title="Close panel">✕</button>
        </div>
        <div class="ev-module-content">
          ${innerHtml}
          <div class="ev-resize-handle"></div>
        </div>`;
    }
  }

  // ===== REGISTRY =====
  const registry = {
    _mods: {},
    register(Cls) { this._mods[Cls.id] = Cls; },
    get(id) { return this._mods[id]; },
    all() { return Object.values(this._mods); }
  };

  // ===== CANVAS =====
  const Canvas = (() => {
    let editMode = false;
    const instances = {};
    let dragging = null, ghostEl = null, dragOffX = 0, dragOffY = 0;

    function setEditMode(on) {
      editMode = on;
      const hint = document.getElementById('ev-edit-hint');
      if (hint) hint.style.display = on ? 'flex' : 'none';
      document.getElementById('ev-canvas')?.classList.toggle('edit-mode', on);
      document.querySelectorAll('.nav-slot, .chat-slot').forEach(s => s.classList.toggle('edit-mode', on));
    }

    function mountModule(id, containerEl, config = {}) {
      const Cls = registry.get(id);
      if (!Cls) { console.warn('EV: unknown module', id); return null; }
      containerEl.setAttribute('data-module-type', id);
      const mod = new Cls(containerEl, config);
      mod.mount();  // module renders its own innerHTML

      const instId = id + '_' + Date.now();
      instances[instId] = { module: mod, el: containerEl, id };

      // Inject chrome overlay AFTER mount (so innerHTML doesn't wipe it)
      // Only for canvas modules, not nav/chat slots
      if (!config.slot) {
        containerEl.classList.add('ev-module');
        const bar = document.createElement('div');
        bar.className = 'ev-module-bar';
        bar.innerHTML = `
          <span class="ev-drag-handle"><span></span><span></span><span></span></span>
          <span class="ev-module-label">${Cls.label || id}</span>
          <button class="ev-module-close" title="Close panel">✕</button>`;
        containerEl.appendChild(bar);

        const rh = document.createElement('div');
        rh.className = 'ev-resize-handle';
        containerEl.appendChild(rh);

        bar.querySelector('.ev-module-close').addEventListener('click', () => {
          if (editMode) unmountInstance(instId);
        });
        _wireDrag(bar.querySelector('.ev-drag-handle'), containerEl);
        _wireResize(rh, containerEl, Cls, mod);
      }

      return instId;
    }

    function unmountInstance(instId) {
      const inst = instances[instId];
      if (!inst) return;
      inst.module.unmount();
      inst.el.remove();
      delete instances[instId];
      updatePalette();
    }

    function _wireDrag(handle, modEl) {
      handle.addEventListener('pointerdown', e => {
        if (!editMode) return;
        e.preventDefault();
        handle.setPointerCapture(e.pointerId);
        dragging = modEl;
        const rect = modEl.getBoundingClientRect();
        dragOffX = e.clientX - rect.left;
        dragOffY = e.clientY - rect.top;
        modEl.style.opacity = '0.7';
        modEl.style.zIndex = '1000';
        modEl.style.boxShadow = '0 8px 32px rgba(0,0,0,0.5)';
        modEl.style.border = '1px solid var(--accent)';
      });

      handle.addEventListener('pointermove', e => {
        if (!dragging || dragging !== modEl) return;
        e.preventDefault();
        const canvas = document.getElementById('ev-canvas');
        if (!canvas) return;
        const canvasRect = canvas.getBoundingClientRect();
        const x = e.clientX - canvasRect.left - dragOffX;
        const y = e.clientY - canvasRect.top - dragOffY + canvas.scrollTop;
        // Move in flow (simplified: reorder siblings by pointer Y)
        const siblings = Array.from(canvas.children).filter(c => c !== modEl && c.classList.contains('ev-module'));
        for (const sib of siblings) {
          const sr = sib.getBoundingClientRect();
          const mid = sr.top + sr.height / 2;
          if (e.clientY < mid) {
            canvas.insertBefore(modEl, sib);
            break;
          }
        }
      });

      handle.addEventListener('pointerup', () => {
        if (dragging === modEl) {
          modEl.style.opacity = '';
          modEl.style.zIndex = '';
          modEl.style.boxShadow = '';
          modEl.style.border = '';
          dragging = null;
        }
      });
    }

    function _wireResize(rh, modEl, Cls, modInst) {
      const SIZES = ['S', 'M', 'L', 'XL'];
      const SIZE_MIN_W = { S: 0, M: 420, L: 580, XL: 800 };
      rh.addEventListener('pointerdown', e => {
        if (!editMode) return;
        e.preventDefault();
        e.stopPropagation();
        rh.setPointerCapture(e.pointerId);
        const startH = modEl.offsetHeight;
        const startY = e.clientY;

        rh.addEventListener('pointermove', onMove);
        rh.addEventListener('pointerup', onUp);

        function onMove(ev) {
          const newH = Math.max(80, startH + (ev.clientY - startY));
          modEl.style.height = newH + 'px';
          // Infer size from width
          const w = modEl.offsetWidth;
          const supported = Cls.supportedSizes || SIZES;
          let best = supported[0];
          for (const s of supported) {
            if (w >= (SIZE_MIN_W[s] || 0)) best = s;
          }
          modEl.setAttribute('data-size', best);
          modInst.resize(best);
        }

        function onUp() {
          rh.removeEventListener('pointermove', onMove);
          rh.removeEventListener('pointerup', onUp);
        }
      });
    }

    function updatePalette() {
      const list = document.getElementById('ev-palette-list');
      if (!list) return;
      const active = new Set(Object.values(instances).map(i => i.id));
      list.innerHTML = registry.all().map(M => `
        <div class="palette-item ${active.has(M.id) ? 'active' : ''}">
          <span>${M.label}</span>
          ${active.has(M.id)
            ? '<span class="palette-badge">Active</span>'
            : `<button class="btn btn-ghost palette-add" data-mod-id="${M.id}">+ Add</button>`}
        </div>`).join('');
      list.querySelectorAll('.palette-add').forEach(btn => {
        btn.addEventListener('click', () => {
          const canvas = document.getElementById('ev-canvas');
          const el = document.createElement('div');
          canvas.appendChild(el);
          mountModule(btn.dataset.modId, el);
          updatePalette();
        });
      });
    }

    return {
      setEditMode,
      mountModule,
      unmountInstance,
      updatePalette,
      get editMode() { return editMode; }
    };
  })();

  window.EV = { Store, API, Module, registry, Canvas };
})();
