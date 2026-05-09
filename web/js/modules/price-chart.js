(() => {
  const CSS_ID = 'ev-price-chart-css';
  const CSS = `
.pc-wrap{display:flex;flex-direction:column;height:100%;min-height:200px;background:var(--panel);border-radius:6px;overflow:hidden;position:relative;}
.pc-header{display:flex;align-items:center;gap:8px;padding:8px 12px;border-bottom:1px solid var(--border);flex-shrink:0;background:var(--panel);}
.pc-title{font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--text-faint);font-weight:600;flex:1;}
.pc-tf-btns{display:flex;gap:2px;}
.pc-tf-btn{font-size:10px;padding:2px 8px;border-radius:3px;border:1px solid var(--border);background:transparent;color:var(--text-dim);cursor:pointer;transition:all 0.1s;}
.pc-tf-btn:hover{background:var(--panel-2);color:var(--text);}
.pc-tf-btn.active{background:var(--accent);color:#fff;border-color:var(--accent);}
.pc-maximize-btn{display:flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:3px;border:1px solid var(--border);background:transparent;color:var(--text-faint);cursor:pointer;font-size:11px;transition:all 0.1s;flex-shrink:0;}
.pc-maximize-btn:hover{background:var(--panel-2);color:var(--text);}
.pc-body{flex:1;position:relative;min-height:0;}
.pc-chart-container{width:100%;height:100%;}
.pc-state{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:8px;font-size:12px;color:var(--text-dim);}
.pc-spinner{width:20px;height:20px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:pc-spin 0.7s linear infinite;}
@keyframes pc-spin{to{transform:rotate(360deg);}}
.pc-err-icon{font-size:20px;opacity:0.4;}
.pc-pattern-badge{position:absolute;top:8px;left:8px;font-size:10px;padding:2px 7px;border-radius:3px;font-weight:600;letter-spacing:0.5px;pointer-events:none;z-index:10;}
.maximized .pc-wrap{border-radius:0;}
.chart-toggles{display:flex;gap:4px;padding:4px 8px;border-bottom:1px solid var(--border);flex-shrink:0;background:var(--panel);}
.chart-tog-btn{font-size:9px;padding:2px 8px;border-radius:3px;border:1px solid var(--border);background:transparent;color:var(--text-faint);cursor:pointer;font-family:var(--font-mono,'SF Mono',monospace);letter-spacing:0.8px;transition:all 0.1s;}
.chart-tog-btn:hover{color:var(--text);border-color:var(--accent-dim);}
.chart-tog-btn.active{color:var(--accent);border-color:rgba(94,227,161,0.4);background:rgba(94,227,161,0.06);}
`;

  function injectCSS() {
    if (document.getElementById(CSS_ID)) return;
    const s = document.createElement('style');
    s.id = CSS_ID;
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function getThemeColors() {
    const cs = getComputedStyle(document.documentElement);
    return {
      bg: cs.getPropertyValue('--bg-primary').trim() || '#0d1117',
      panel: cs.getPropertyValue('--panel').trim() || '#161b22',
      text: cs.getPropertyValue('--text').trim() || '#e6edf3',
      textDim: cs.getPropertyValue('--text-dim').trim() || '#8b949e',
      border: cs.getPropertyValue('--border').trim() || '#30363d',
    };
  }

  const PATTERN_LABELS = {
    breakout:             { text: 'Breakout ↑',         color: '#22c55e', shape: 'arrowUp' },
    pullback_in_trend:    { text: 'Pullback to Support',  color: '#22c55e', shape: 'arrowUp'  },
    compression_break:    { text: 'Compression Break',  color: '#a855f7', shape: 'arrowUp' },
    ema_reclaim:          { text: 'EMA Reclaim',         color: '#22c55e', shape: 'arrowUp' },
    base_breakout:        { text: 'Base Breakout',       color: '#22c55e', shape: 'arrowUp' },
    oversold_bounce:      { text: 'Oversold Bounce',     color: '#3b82f6', shape: 'arrowUp' },
    failed_breakdown:     { text: 'Failed Breakdown',    color: '#22c55e', shape: 'arrowUp' },
    bullish_reversal:     { text: 'Bullish Rev ↑',       color: '#22c55e', shape: 'arrowUp' },
    bearish_reversal:     { text: 'Bearish Rev ↓',       color: '#ef4444', shape: 'arrowDown' },
    breakdown:            { text: 'Breakdown ↓',         color: '#ef4444', shape: 'arrowDown' },
    rally_in_downtrend:   { text: 'Rally (Short)',        color: '#f97316', shape: 'arrowDown' },
    compression_break_down: { text: 'Compression ↓',    color: '#a855f7', shape: 'arrowDown' },
    ema_rejection:        { text: 'EMA Rejection',       color: '#ef4444', shape: 'arrowDown' },
    base_breakdown:       { text: 'Base Breakdown ↓',    color: '#ef4444', shape: 'arrowDown' },
    overbought_reversal:  { text: 'Overbought Rev ↓',   color: '#ef4444', shape: 'arrowDown' },
    failed_breakout:      { text: 'Failed Breakout ↓',  color: '#f97316', shape: 'arrowDown' },
  };

  function patternBadgeHtml(pattern) {
    if (!pattern || !pattern.type || pattern.type === 'no_pattern') return '';
    const info = PATTERN_LABELS[pattern.type];
    if (!info) return '';
    const pct = pattern.confidence ? ` ${Math.round(pattern.confidence * 100)}%` : '';
    return `<div class="pc-pattern-badge" style="background:${info.color}22;color:${info.color};border:1px solid ${info.color}44;">${info.text}${pct}</div>`;
  }

  const FallbackBase = window.EV?.Module ?? class {
    constructor(el, cfg) { this.el = el; this.config = cfg; this._unsubs = []; }
    mount() {}
    unmount() { this._unsubs.forEach(f => f()); this._unsubs = []; }
    resize(_s) {}
    _sub(k, f) { if (window.EV) this._unsubs.push(window.EV.Store.subscribe(k, f)); }
    _html(h) { this.el.innerHTML = h; }
    _qs(s) { return this.el.querySelector(s); }
    _qsa(s) { return this.el.querySelectorAll(s); }
  };

  class PriceChartModule extends FallbackBase {
    mount() {
      injectCSS();
      this._tf = '1d';
      this._ticker = null;
      this._chart = null;
      this._series = {};
      this._maximized = false;
      this._lastData = null;
      this._toggleState = {
        ema21:   JSON.parse(localStorage.getItem('chart_ema21')    ?? 'true'),
        ema50:   JSON.parse(localStorage.getItem('chart_ema50')    ?? 'true'),
        signals: JSON.parse(localStorage.getItem('chart_signals')  ?? 'true'),
      };

      this._render();
      this._bindHeader();

      // subscribe to store
      this._sub('selectedTicker', ticker => {
        if (!ticker) { this._ticker = null; this._showState('empty', 'Select a pick to view chart'); return; }
        if (ticker !== this._ticker) { this._ticker = ticker; this._load(); }
      });
      this._sub('selectedPick', pick => {
        const ticker = pick?.ticker;
        if (!ticker) { this._ticker = null; this._showState('empty', 'Select a pick to view chart'); return; }
        if (ticker !== this._ticker) { this._ticker = ticker; this._load(); }
      });

      // initial ticker
      const initTicker = window.EV?.Store.get('selectedTicker') ?? window.EV?.Store.get('selectedPick')?.ticker;
      if (initTicker) {
        this._ticker = initTicker;
        this._load();
      } else {
        this._showState('empty', 'Select a pick to view chart');
      }

      // escape key to close maximize
      this._onEscape = (e) => { if (e.key === 'Escape' && this._maximized) this._toggleMaximize(); };
      document.addEventListener('keydown', this._onEscape);

      // ResizeObserver: fire _resizeChart when container gets real dimensions
      const body = this._qs('#pc-chart-body');
      if (body && window.ResizeObserver) {
        this._ro = new ResizeObserver(() => this._resizeChart());
        this._ro.observe(body);
      }

      // MutationObserver: rebuild chart when data-theme changes (light/dark switch)
      this._themeObs = new MutationObserver(() => {
        if (this._lastData) this._buildChart(this._lastData);
      });
      this._themeObs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    }

    unmount() {
      super.unmount();
      if (this._onEscape) document.removeEventListener('keydown', this._onEscape);
      if (this._chart) { this._chart.remove(); this._chart = null; }
      if (this._ro) { this._ro.disconnect(); this._ro = null; }
      if (this._themeObs) { this._themeObs.disconnect(); this._themeObs = null; }
    }

    resize(_size) {
      this._resizeChart();
    }

    _render() {
      const ts = this._toggleState;
      this.el.innerHTML = `
        <div class="pc-wrap">
          <div class="pc-header">
            <span class="pc-title" id="pc-title">PRICE CHART</span>
            <div class="pc-tf-btns">
              <button class="pc-tf-btn active" data-tf="1d">1D</button>
              <button class="pc-tf-btn" data-tf="1wk">1W</button>
            </div>
            <button class="pc-maximize-btn" id="pc-max-btn" title="Maximize">⤢</button>
          </div>
          <div class="chart-toggles">
            <button class="chart-tog-btn${ts.ema21 ? ' active' : ''}" data-toggle="ema21">EMA21</button>
            <button class="chart-tog-btn${ts.ema50 ? ' active' : ''}" data-toggle="ema50">EMA50</button>
            <button class="chart-tog-btn${ts.signals ? ' active' : ''}" data-toggle="signals">BACKTEST</button>
            <button id="pc-all-off" class="chart-tog-btn" style="margin-left:auto">ALL OFF</button>
          </div>
          <div class="pc-body" id="pc-chart-body">
            <div class="pc-chart-container" id="pc-chart-container"></div>
            <div class="pc-state" id="pc-state" style="display:none;"></div>
          </div>
        </div>`;
    }

    _bindHeader() {
      this._qs('.pc-tf-btns').addEventListener('click', e => {
        const btn = e.target.closest('.pc-tf-btn');
        if (!btn) return;
        const tf = btn.dataset.tf;
        if (tf === this._tf) return;
        this._tf = tf;
        this._qsa('.pc-tf-btn').forEach(b => b.classList.toggle('active', b.dataset.tf === tf));
        this._load();
      });

      this._qs('#pc-max-btn').addEventListener('click', () => this._toggleMaximize());

      this._qs('.chart-toggles').addEventListener('click', e => {
        const btn = e.target.closest('.chart-tog-btn');
        if (!btn) return;
        if (btn.id === 'pc-all-off') {
          Object.keys(this._toggleState).forEach(key => {
            this._toggleState[key] = false;
            localStorage.setItem(`chart_${key}`, 'false');
            this._applyToggle(key);
          });
          this._qsa('.chart-tog-btn[data-toggle]').forEach(b => b.classList.remove('active'));
          return;
        }
        const key = btn.dataset.toggle;
        if (!key) return;
        this._toggleState[key] = !this._toggleState[key];
        localStorage.setItem(`chart_${key}`, JSON.stringify(this._toggleState[key]));
        btn.classList.toggle('active', this._toggleState[key]);
        this._applyToggle(key);
      });
    }

    _applyToggle(key) {
      if (key === 'ema21' && this._series.ema21) {
        this._series.ema21.applyOptions({ visible: this._toggleState.ema21 });
      } else if (key === 'ema50' && this._series.ema50) {
        this._series.ema50.applyOptions({ visible: this._toggleState.ema50 });
      } else if (key === 'signals') {
        // Re-apply markers: clear if toggled off, restore if on
        const candle = this._series.candle;
        if (!candle) return;
        if (!this._toggleState.signals) {
          candle.setMarkers([]);
        } else if (this._lastSignalMarkers) {
          candle.setMarkers(this._lastSignalMarkers);
        }
      }
    }

    _toggleMaximize() {
      this._maximized = !this._maximized;
      this.el.classList.toggle('maximized', this._maximized);
      if (this._maximized) {
        this._preMaxStyle = this.el.style.cssText;
        this.el.style.cssText = 'position:fixed;inset:0;z-index:1000;';
      } else {
        this.el.style.cssText = this._preMaxStyle || '';
      }
      const btn = this._qs('#pc-max-btn');
      if (btn) btn.textContent = this._maximized ? '⤡' : '⤢';
      requestAnimationFrame(() => this._resizeChart());
    }

    _showState(type, msg) {
      const stateEl = this._qs('#pc-state');
      const chartEl = this._qs('#pc-chart-container');
      if (!stateEl) return;
      if (type === 'none') {
        stateEl.style.display = 'none';
        if (chartEl) chartEl.style.visibility = 'visible';
        return;
      }
      if (chartEl) chartEl.style.visibility = 'hidden';
      if (type === 'loading') {
        stateEl.innerHTML = '<div class="pc-spinner"></div>';
      } else if (type === 'error') {
        stateEl.innerHTML = `<div class="pc-err-icon">⚠</div><span>${msg || 'No chart data'}</span>`;
      } else {
        stateEl.innerHTML = `<span>${msg || ''}</span>`;
      }
      stateEl.style.display = 'flex';
    }

    async _load() {
      if (!this._ticker) return;
      this._showState('loading');

      const titleEl = this._qs('#pc-title');
      if (titleEl) titleEl.textContent = `${this._ticker} · ${this._tf.toUpperCase()}`;

      // remove old pattern badge
      const oldBadge = this._qs('.pc-pattern-badge');
      if (oldBadge) oldBadge.remove();

      let data;
      try {
        data = await (window.EV?.API.get(`/api/chart/${this._ticker}?tf=${this._tf}`) ?? Promise.reject(new Error('EV.API not ready')));
      } catch (err) {
        this._showState('error', 'No chart data');
        return;
      }

      if (!data?.candles?.length) {
        this._showState('error', 'No price data');
        return;
      }

      this._lastData = data;
      this._lastSignalMarkers = null;
      this._showState('none');
      this._buildChart(data);

      // pattern badge overlay
      const body = this._qs('#pc-chart-body');
      if (body && data.pattern) {
        const badgeHtml = patternBadgeHtml(data.pattern);
        if (badgeHtml) {
          const tmp = document.createElement('div');
          tmp.innerHTML = badgeHtml;
          body.appendChild(tmp.firstElementChild);
        }
      }

      // Load historical signal markers
      this._loadChartSignals(this._ticker);
    }

    async _loadChartSignals(ticker) {
      try {
        const signals = await (window.EV?.API.get(`/api/chart/${ticker}/signals`) ?? Promise.resolve([]));
        if (!signals || !signals.length) return;
        const candle = this._series.candle;
        if (!candle) return;

        const markers = signals.map(s => ({
          time: s.scan_date,
          position: s.direction === 'long' ? 'belowBar' : 'aboveBar',
          color: s.direction === 'long' ? '#00ff99' : '#ff2d55',
          shape: s.direction === 'long' ? 'arrowUp' : 'arrowDown',
          text: s.setup_type.replace(/_/g, ' '),
        }));

        this._lastSignalMarkers = markers;
        if (this._toggleState.signals) {
          candle.setMarkers(markers);
        }
      } catch (_) {}
    }

    _buildChart(data) {
      const container = this._qs('#pc-chart-container');
      if (!container) return;

      if (this._chart) {
        this._chart.remove();
        this._chart = null;
        this._series = {};
      }

      const LC = window.LightweightCharts;
      if (!LC) {
        this._showState('error', 'Chart library not loaded');
        return;
      }

      const colors = getThemeColors();
      const w = container.clientWidth || container.offsetWidth || 600;
      const h = container.clientHeight || container.offsetHeight || 300;

      this._chart = LC.createChart(container, {
        width: w,
        height: h,
        layout: {
          background: { type: LC.ColorType?.Solid ?? 'solid', color: colors.panel },
          textColor: colors.textDim,
          fontSize: 11,
        },
        grid: {
          vertLines: { color: colors.border + '55' },
          horzLines: { color: colors.border + '55' },
        },
        crosshair: { mode: LC.CrosshairMode?.Normal ?? 1 },
        rightPriceScale: { borderColor: colors.border },
        timeScale: { borderColor: colors.border, timeVisible: true, rightOffset: 12 },
        handleScroll: true,
        handleScale: true,
      });

      // Candlestick
      const candleSeries = this._chart.addCandlestickSeries({
        upColor: '#22c55e',
        downColor: '#ef4444',
        borderUpColor: '#22c55e',
        borderDownColor: '#ef4444',
        wickUpColor: '#22c55e',
        wickDownColor: '#ef4444',
      });
      candleSeries.setData(data.candles);
      this._series.candle = candleSeries;

      const ind = data.indicators || {};

      // EMA 21
      if (ind.ema21?.length) {
        const s = this._chart.addLineSeries({ color: '#f59e0b', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title: '', visible: this._toggleState.ema21 });
        s.setData(ind.ema21);
        this._series.ema21 = s;
      }

      // EMA 50
      if (ind.ema50?.length) {
        const s = this._chart.addLineSeries({ color: '#3b82f6', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title: '', visible: this._toggleState.ema50 });
        s.setData(ind.ema50);
        this._series.ema50 = s;
      }

      // BB upper
      if (ind.bb_upper?.length) {
        const s = this._chart.addLineSeries({
          color: 'rgba(168,85,247,0.5)',
          lineWidth: 1,
          lineStyle: LC.LineStyle?.Dashed ?? 1,
          priceLineVisible: false,
          lastValueVisible: false,
          title: 'BB+',
        });
        s.setData(ind.bb_upper);
        this._series.bb_upper = s;
      }

      // BB lower
      if (ind.bb_lower?.length) {
        const s = this._chart.addLineSeries({
          color: 'rgba(168,85,247,0.5)',
          lineWidth: 1,
          lineStyle: LC.LineStyle?.Dashed ?? 1,
          priceLineVisible: false,
          lastValueVisible: false,
          title: 'BB−',
        });
        s.setData(ind.bb_lower);
        this._series.bb_lower = s;
      }

      // GEX horizontal lines on the candle series
      const gex = data.gex_levels || {};
      if (gex.call_wall) {
        candleSeries.createPriceLine({ price: gex.call_wall, color: '#22c55e', lineWidth: 1, lineStyle: LC.LineStyle?.Dashed ?? 1, axisLabelVisible: true, title: 'Call Wall' });
      }
      if (gex.put_wall) {
        candleSeries.createPriceLine({ price: gex.put_wall, color: '#ef4444', lineWidth: 1, lineStyle: LC.LineStyle?.Dashed ?? 1, axisLabelVisible: true, title: 'Put Wall' });
      }
      if (gex.gamma_flip) {
        candleSeries.createPriceLine({ price: gex.gamma_flip, color: '#f59e0b', lineWidth: 1, lineStyle: LC.LineStyle?.Solid ?? 0, axisLabelVisible: true, title: 'Flip' });
      }

      // Entry zone + stop level (from today's pick data)
      const ez = data.entry_zone || {};
      if (ez.low) {
        candleSeries.createPriceLine({ price: ez.low, color: 'rgba(34,197,94,0.7)', lineWidth: 1, lineStyle: LC.LineStyle?.Dashed ?? 1, axisLabelVisible: true, title: 'Entry' });
      }
      if (ez.high && ez.high !== ez.low) {
        candleSeries.createPriceLine({ price: ez.high, color: 'rgba(34,197,94,0.5)', lineWidth: 1, lineStyle: LC.LineStyle?.Dashed ?? 1, axisLabelVisible: true, title: 'Entry Hi' });
      }
      if (data.stop) {
        candleSeries.createPriceLine({ price: data.stop, color: 'rgba(239,68,68,0.8)', lineWidth: 2, lineStyle: LC.LineStyle?.Dashed ?? 1, axisLabelVisible: true, title: 'Stop' });
      }

      // Pattern marker on last candle
      if (data.pattern && data.pattern.type !== 'no_pattern') {
        const info = PATTERN_LABELS[data.pattern.type];
        if (info && data.candles.length) {
          const last = data.candles[data.candles.length - 1];
          candleSeries.setMarkers([{
            time: last.time,
            position: info.shape === 'arrowUp' ? 'belowBar' : 'aboveBar',
            color: info.color,
            shape: info.shape,
            text: info.text,
          }]);
        }
      }

      this._chart.timeScale().fitContent();
      this._resizeChart();
    }

    _resizeChart() {
      if (!this._chart) return;
      const container = this._qs('#pc-chart-container');
      if (!container) return;
      const body = this._qs('#pc-chart-body');
      const w = body ? body.clientWidth : container.clientWidth;
      const h = body ? body.clientHeight : container.clientHeight;
      if (w > 0 && h > 0) {
        this._chart.resize(w, h);
      }
    }
  }

  PriceChartModule.id = 'price-chart';
  PriceChartModule.label = 'Price Chart';
  PriceChartModule.defaultSize = 'L';
  PriceChartModule.supportedSizes = ['M', 'L', 'XL'];

  if (window.EV?.registry) {
    window.EV.registry.register(PriceChartModule);
  }
  window.PriceChartModule = PriceChartModule;
})();
