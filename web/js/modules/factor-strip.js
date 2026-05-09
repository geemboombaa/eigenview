(() => {
  const CSS_ID = 'ev-factor-strip-css';
  const CSS = `
.fs-wrap{display:flex;flex-direction:column;height:100%;overflow:hidden;background:var(--panel);}
.fs-top{display:flex;align-items:center;gap:6px;padding:7px 10px;flex-shrink:0;border-top:1px solid var(--border);overflow-x:auto;scrollbar-width:none;}
.fs-top::-webkit-scrollbar{display:none;}
.fs-dot-btn{display:flex;align-items:center;gap:5px;padding:4px 9px;border-radius:4px;background:transparent;border:1px solid var(--border);cursor:pointer;font-size:9px;letter-spacing:0.6px;color:var(--text-faint);font-family:var(--font-mono);white-space:nowrap;transition:all 0.1s;flex-shrink:0;}
.fs-dot-btn:hover{border-color:var(--text-faint);color:var(--text);}
.fs-dot-btn.expanded{background:var(--panel-2);color:var(--text);}
.fs-dot-btn.fired{color:var(--text);border-color:rgba(34,197,94,0.3);}
.fs-dot{width:7px;height:7px;border-radius:50%;background:var(--border);flex-shrink:0;transition:background 0.2s;}
.fs-dot-btn.fired .fs-dot{background:#22c55e;}
.fs-sep{width:1px;height:16px;background:var(--border);flex-shrink:0;}
.fs-pick-label{font-size:10px;color:var(--text-faint);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1;min-width:0;}
.fs-pick-label strong{color:var(--text);}
.fs-detail{flex:1;min-height:0;overflow-y:auto;padding:10px 14px 8px;}
.fs-empty-msg{padding:16px 0;font-size:11px;color:var(--text-faint);}
.fs-chk-title{font-size:10px;font-weight:600;letter-spacing:0.5px;color:var(--text);margin-bottom:8px;}
.fs-chk{display:flex;align-items:center;gap:7px;padding:3px 0;}
.fs-chk-icon{width:14px;height:14px;border-radius:50%;font-size:9px;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-weight:700;}
.fs-ck-y{background:rgba(34,197,94,0.15);color:#22c55e;}
.fs-ck-n{background:rgba(239,68,68,0.1);color:#ef4444;}
.fs-chk-label{font-size:11px;color:var(--text-dim);flex:1;}
.fs-chk-val{font-size:10px;color:var(--text-faint);font-family:var(--font-mono);}
.fs-narrative{font-size:11px;color:var(--text-dim);line-height:1.5;}
.fs-kv{display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;}
.fs-kv-item{font-size:10px;color:var(--text-faint);}
.fs-kv-item strong{color:var(--text);}
`;

  const FACTOR_META = [
    { id: 'technical', label: 'TA'        },
    { id: 'gex',       label: 'GEX'       },
    { id: 'flow',      label: 'FLOW'      },
    { id: 'dormant',   label: 'DORM'      },
    { id: 'sentiment', label: 'SENTIMENT' },
  ];

  const FACTOR_FULL = {
    technical: 'Technical Analysis', gex: 'Gamma Exposure',
    flow: 'Options Flow', dormant: 'Dormant Bets', sentiment: 'Sentiment',
  };

  const PATTERN_NAMES = {
    breakout:'Breakout', pullback_in_trend:'Pullback to Support',
    compression_break:'Squeeze Breakout', ema_reclaim:'EMA Reclaim',
    base_breakout:'Stage 2 Breakout', oversold_bounce:'Oversold Bounce',
    failed_breakdown:'Failed Breakdown', bullish_reversal:'Bullish Reversal',
    breakdown:'Breakdown', rally_in_downtrend:'Dead-Cat Bounce',
    compression_break_down:'Squeeze Breakdown', ema_rejection:'EMA Rejection',
    base_breakdown:'Stage 2 Breakdown', overbought_reversal:'Overbought Reversal',
    failed_breakout:'Failed Breakout', bearish_reversal:'Bearish Reversal',
    no_pattern:'No Pattern',
    flag_continuation:'Flag Continuation', bull_flag:'Bull Flag',
    pullback_deep:'Deep Pullback', pullback_to_structure:'Pullback to Structure',
    compression_break_down:'Squeeze Breakdown',
    base_breakdown:'Stage 2 Breakdown', base_breakout:'Stage 2 Breakout',
    choch_bullish:'CHoCH Bullish', choch_bearish:'CHoCH Bearish',
    bos_bullish:'BOS Bullish', bos_bearish:'BOS Bearish',
    bb_mean_reversion_long:'BB Mean Reversion Long', bb_mean_reversion_short:'BB Mean Reversion Short',
    ema200_snap_long:'EMA200 Snap Long', ema200_snap_short:'EMA200 Snap Short',
  };

  function _chk(label, pass, val) { return { label, pass, val }; }

  // Map internal trend codes to readable strings
  const TREND_FMT = {
    bullish: 'Bullish', bearish: 'Bearish', sideways: 'Sideways',
    bearish_strong: 'Strongly Bearish', bearish_weak: 'Weakly Bearish',
    bullish_strong: 'Strongly Bullish',
  };
  const tf = t => TREND_FMT[t] || (t ? t.replace(/_/g, ' ') : '—');
  const vf = v => v != null ? `${Number(v).toFixed(1)}×` : '—';
  const rf = v => v != null ? `${Math.round(v)}` : '—';

  // Only data-driven checks — no hardcoded true/false
  const TA_CHECKS = {
    breakout: d => [
      _chk('EMA stack bullish (21 > 50)',   d.trend === 'bullish',                         tf(d.trend)),
      _chk('Volume surge (>1.5× avg)',       (d.vol_ratio||0) > 1.5,                       vf(d.vol_ratio)),
      _chk('Weekly trend bullish',           d.weekly_trend === 'bullish',                  tf(d.weekly_trend)),
      _chk('RSI below 78 (not extended)',    !d.rsi || d.rsi < 78,                         rf(d.rsi)),
      _chk('ADX trending (>20)',             (d.adx||0) > 20,                              rf(d.adx)),
    ],
    pullback_in_trend: d => [
      _chk('Uptrend intact (EMA 21 > 50)',   d.trend === 'bullish',                         tf(d.trend)),
      _chk('Weekly trend bullish',           d.weekly_trend === 'bullish',                  tf(d.weekly_trend)),
      _chk('RSI in dip zone (38–57)',        d.rsi != null && d.rsi >= 38 && d.rsi <= 57,  rf(d.rsi)),
      _chk('Volume light on pullback',       (d.vol_ratio||0) < 1.5,                       vf(d.vol_ratio)),
      _chk('ADX has trend (>15)',            (d.adx||0) > 15,                              rf(d.adx)),
    ],
    compression_break: d => [
      _chk('Volatility contracted',          d.vol_character === 'declining',               tf(d.vol_character)),
      _chk('Volume surge on break (>1.5×)', (d.vol_ratio||0) > 1.5,                        vf(d.vol_ratio)),
      _chk('RSI not extended (<78)',         !d.rsi || d.rsi < 78,                         rf(d.rsi)),
      _chk('Weekly trend bullish',           d.weekly_trend === 'bullish',                  tf(d.weekly_trend)),
    ],
    ema_reclaim: d => [
      _chk('Trend recovering (not bearish)', d.trend !== 'bearish',                         tf(d.trend)),
      _chk('Volume on reclaim (>1.1×)',      (d.vol_ratio||0) > 1.1,                       vf(d.vol_ratio)),
      _chk('Weekly trend bullish',           d.weekly_trend === 'bullish',                  tf(d.weekly_trend)),
    ],
    base_breakout: d => [
      _chk('Weekly trend bullish',           d.weekly_trend === 'bullish',                  tf(d.weekly_trend)),
      _chk('Volatility contracted in base',  d.vol_character === 'declining',               tf(d.vol_character)),
      _chk('ADX low — range-bound base',     (d.adx||0) < 25,                              rf(d.adx)),
    ],
    oversold_bounce: d => [
      _chk('RSI deeply oversold (<32)',      d.rsi != null && d.rsi < 32,                  rf(d.rsi)),
      _chk('Volume on bounce (>1.2×)',       (d.vol_ratio||0) > 1.2,                       vf(d.vol_ratio)),
      _chk('Bullish RSI divergence',         !!d.bull_divergence,                           d.bull_divergence ? 'yes' : 'no'),
    ],
    bullish_reversal: d => [
      _chk('Bullish RSI divergence',         !!d.bull_divergence,                           d.bull_divergence ? 'yes' : 'no'),
      _chk('Volume exhaustion spike (>1.8×)',(d.vol_ratio||0) > 1.8,                       vf(d.vol_ratio)),
      _chk('RSI not yet overbought (<55)',   !d.rsi || d.rsi < 55,                         rf(d.rsi)),
      _chk('ADX trending (>15)',             (d.adx||0) > 15,                              rf(d.adx)),
    ],
    failed_breakdown: d => [
      _chk('High-volume reversal (>1.5×)',   (d.vol_ratio||0) > 1.5,                       vf(d.vol_ratio)),
      _chk('Weekly trend bullish',           d.weekly_trend === 'bullish',                  tf(d.weekly_trend)),
      _chk('RSI not extended (<70)',         !d.rsi || d.rsi < 70,                         rf(d.rsi)),
    ],
    // ─── SHORT patterns ───────────────────────────────────────────────────────
    breakdown: d => [
      _chk('Downtrend (EMA 21 < 50)',        d.trend === 'bearish',                         tf(d.trend)),
      _chk('Volume surge (>1.5×)',           (d.vol_ratio||0) > 1.5,                       vf(d.vol_ratio)),
      _chk('Weekly not bullish',             d.weekly_trend !== 'bullish',                  tf(d.weekly_trend)),
      _chk('RSI not extreme oversold (>25)', !d.rsi || d.rsi > 25,                         rf(d.rsi)),
    ],
    rally_in_downtrend: d => [
      _chk('Downtrend intact (EMA 21 < 50)', d.trend === 'bearish',                         tf(d.trend)),
      _chk('RSI in bounce zone (43–62)',     d.rsi != null && d.rsi >= 43 && d.rsi <= 62,  rf(d.rsi)),
      _chk('Volume low on rally',            d.vol_character === 'declining',               tf(d.vol_character)),
      _chk('ADX has trend (>15)',            (d.adx||0) > 15,                              rf(d.adx)),
    ],
    compression_break_down: d => [
      _chk('Volatility contracted',          d.vol_character === 'declining',               tf(d.vol_character)),
      _chk('Volume expansion on break (>1.5×)', (d.vol_ratio||0) > 1.5,                    vf(d.vol_ratio)),
      _chk('Weekly not bullish',             d.weekly_trend !== 'bullish',                  tf(d.weekly_trend)),
    ],
    ema_rejection: d => [
      _chk('Downtrend (EMA 21 < 50)',        d.trend === 'bearish',                         tf(d.trend)),
      _chk('Volume on rejection (>1.1×)',    (d.vol_ratio||0) > 1.1,                       vf(d.vol_ratio)),
      _chk('Weekly bearish context',         d.weekly_trend !== 'bullish',                  tf(d.weekly_trend)),
    ],
    base_breakdown: d => [
      _chk('Weekly not bullish',             d.weekly_trend !== 'bullish',                  tf(d.weekly_trend)),
      _chk('Volatility low — quiet base',    d.vol_character === 'declining',               tf(d.vol_character)),
    ],
    overbought_reversal: d => [
      _chk('In uptrend (reversal target)',   d.trend === 'bullish',                         tf(d.trend)),
      _chk('RSI overbought (>68)',           d.rsi != null && d.rsi > 68,                  rf(d.rsi)),
      _chk('Volume on down day (>1.2×)',     (d.vol_ratio||0) > 1.2,                       vf(d.vol_ratio)),
      _chk('Bearish RSI divergence',         !!d.bear_divergence,                           d.bear_divergence ? 'yes' : 'no'),
    ],
    failed_breakout: d => [
      _chk('Trend fading (not bullish)',     d.trend !== 'bullish',                         tf(d.trend)),
      _chk('Volume confirmation (>1.2×)',    (d.vol_ratio||0) > 1.2,                       vf(d.vol_ratio)),
      _chk('ADX present (>15)',              (d.adx||0) > 15,                              rf(d.adx)),
    ],
    bearish_reversal: d => [
      _chk('In uptrend (reversal target)',   d.trend === 'bullish',                         tf(d.trend)),
      _chk('ADX strong (>25)',               (d.adx||0) > 25,                              rf(d.adx)),
      _chk('Bearish RSI divergence',         !!d.bear_divergence,                           d.bear_divergence ? 'yes' : 'no'),
      _chk('RSI elevated (>72)',             d.rsi != null && d.rsi > 72,                  rf(d.rsi)),
      _chk('Volume spike (>1.6×)',           (d.vol_ratio||0) > 1.6,                       vf(d.vol_ratio)),
    ],
    bull_flag: d => [
      _chk('Uptrend intact (EMA 21 > 50)',   d.trend === 'bullish',                         tf(d.trend)),
      _chk('Prior impulse >5%',              (d.impulse_pct||0) > 5,                        d.impulse_pct != null ? `${d.impulse_pct.toFixed(1)}%` : '—'),
      _chk('Consolidating (vol <1.2×)',      (d.vol_ratio||0) < 1.2,                        vf(d.vol_ratio)),
      _chk('RSI holding (45–65)',            d.rsi != null && d.rsi >= 45 && d.rsi <= 65,  rf(d.rsi)),
      _chk('Weekly trend bullish',           d.weekly_trend === 'bullish',                  tf(d.weekly_trend)),
    ],
    flag_continuation: d => [
      _chk('Prior impulse >5%',              (d.impulse_pct||0) > 5,                        d.impulse_pct != null ? `${d.impulse_pct.toFixed(1)}%` : '—'),
      _chk('Consolidating (vol <1.2×)',      (d.vol_ratio||0) < 1.2,                        vf(d.vol_ratio)),
      _chk('RSI holding (45–65)',            d.rsi != null && d.rsi >= 45 && d.rsi <= 65,  rf(d.rsi)),
      _chk('Weekly not bearish',             d.weekly_trend !== 'bearish',                  tf(d.weekly_trend)),
    ],
  };

  function renderChecklist(factorId, fdata) {
    const d = fdata?.detail || {};
    const fired = !!fdata?.firing;
    const name = FACTOR_FULL[factorId] || factorId;
    const statusClr = fired ? '#22c55e' : 'var(--text-faint)';
    const statusTxt = fired ? 'FIRED' : 'not firing';

    if (factorId === 'technical') {
      const pat = d.pattern || 'no_pattern';
      const pname = PATTERN_NAMES[pat] || pat;
      const conf = d.confidence ? ` · ${Math.round(d.confidence * 100)}% conf` : '';
      const checkFn = TA_CHECKS[pat];
      const checks = checkFn ? checkFn(d) : [];
      if (!checks.length) {
        return `<div class="fs-chk-title">TA · ${pname}${conf}</div><div class="fs-empty-msg">No check data for this pattern.</div>`;
      }
      return `
        <div class="fs-chk-title">TA · ${pname}${conf}</div>
        ${checks.map(c => `
          <div class="fs-chk">
            <span class="fs-chk-icon ${c.pass ? 'fs-ck-y' : 'fs-ck-n'}">${c.pass ? '✓' : '✗'}</span>
            <span class="fs-chk-label">${c.label}</span>
            ${c.val != null ? `<span class="fs-chk-val">${c.val}</span>` : ''}
          </div>`).join('')}`;
    }

    // Non-TA: narrative + key values
    const narrative = fdata?.narrative || '';
    const kvItems = [];
    if (factorId === 'gex') {
      const REGIME_LABELS = { positive:'Positive gamma — price pinned', negative:'Negative gamma — moves amplified', flip_zone:'Near gamma flip — direction unclear' };
      if (d.regime) kvItems.push(`Regime <strong>${REGIME_LABELS[d.regime] || d.regime}</strong>`);
      if (d.gamma_flip) kvItems.push(`Gamma Flip <strong>$${Math.round(d.gamma_flip)}</strong>`);
      if (d.call_wall)  kvItems.push(`Call Wall (resistance) <strong>$${Math.round(d.call_wall)}</strong>`);
      if (d.put_wall)   kvItems.push(`Put Wall (support) <strong>$${Math.round(d.put_wall)}</strong>`);
    } else if (factorId === 'flow') {
      const DIR = { bullish:'Bullish (call buying)', bearish:'Bearish (put buying)', call:'Call flow dominant', put:'Put flow dominant' };
      if (d.flow_direction)          kvItems.push(`Flow direction <strong>${DIR[d.flow_direction] || d.flow_direction}</strong>`);
      if (d.largest_sweep)           kvItems.push(`Largest sweep <strong>$${(d.largest_sweep/1000).toFixed(0)}K</strong>`);
      if (d.dark_pool_cluster_price) kvItems.push(`Dark pool cluster <strong>$${Math.round(d.dark_pool_cluster_price)}</strong>`);
    } else if (factorId === 'dormant') {
      if (d.activation_probability != null) kvItems.push(`Activation probability <strong>${Math.round(d.activation_probability * 100)}%</strong>`);
      if (d.position_age_days)              kvItems.push(`Position age <strong>${d.position_age_days} days</strong>`);
    } else if (factorId === 'sentiment') {
      const SENT_DIR = { positive:'Positive', negative:'Negative', bullish:'Bullish', bearish:'Bearish', neutral:'Neutral' };
      if (d.sentiment_direction)    kvItems.push(`News tone <strong>${SENT_DIR[d.sentiment_direction] || d.sentiment_direction}</strong>`);
      if (d.catalyst_proximity > 0) kvItems.push(`Catalyst in <strong>${Math.round(d.catalyst_proximity)} days</strong>`);
      if (d.top_headline)           kvItems.push(`"${d.top_headline.slice(0, 70)}${d.top_headline.length > 70 ? '…' : ''}"`);
    }

    return `
      <div class="fs-chk-title">${name} · <span style="color:${statusClr}">${statusTxt}</span></div>
      ${narrative ? `<div class="fs-narrative">${narrative}</div>` : ''}
      ${kvItems.length ? `<div class="fs-kv">${kvItems.map(k => `<span class="fs-kv-item">${k}</span>`).join('')}</div>` : (!narrative ? '<div class="fs-empty-msg">No data available for this signal.</div>' : '')}
    `;
  }

  function injectCSS() {
    if (document.getElementById(CSS_ID)) return;
    const s = document.createElement('style');
    s.id = CSS_ID; s.textContent = CSS;
    document.head.appendChild(s);
  }

  const Base = window.EV?.Module ?? class {
    constructor(el, cfg) { this.el = el; this.config = cfg || {}; this._subs = []; }
    mount() {}
    unmount() { this._subs.forEach(u => u()); this._subs = []; }
    resize() {}
    _sub(k, f) { if (window.EV?.Store) this._subs.push(window.EV.Store.subscribe(k, f)); }
    _qs(s) { return this.el.querySelector(s); }
  };

  class FactorStripModule extends Base {
    static id = 'factor-strip';

    mount() {
      injectCSS();
      this._pick = null;
      this._expanded = null;
      this._render(null);

      this._sub('selectedPick', pick => {
        this._pick = pick;
        this._expanded = null;
        (this.el.parentElement || this.el).classList.remove('expanded');
        this._render(pick);
      });

      const init = window.EV?.Store.get('selectedPick');
      if (init) { this._pick = init; this._render(init); }
    }

    _render(pick) {
      if (!pick) {
        this.el.innerHTML = `<div class="fs-wrap"><div class="fs-top"><span class="fs-pick-label">Select a pick to view signals</span></div><div class="fs-detail"></div></div>`;
        return;
      }

      const factors = pick.factors || {};
      const dir = (pick.direction || 'long').toLowerCase();
      const ta = factors.technical;
      const setupName = PATTERN_NAMES[ta?.label || pick.setup_type] || pick.setup_type || '';
      const dirColor = dir === 'short' ? '#ef4444' : '#22c55e';
      const dirLabel = dir === 'short' ? 'SELL' : 'BUY';

      const dotsHtml = FACTOR_META.map(fm => {
        const fdata = factors[fm.id] || {};
        const fired = !!fdata.firing;
        const isExp = this._expanded === fm.id;
        return `<button class="fs-dot-btn${fired ? ' fired' : ''}${isExp ? ' expanded' : ''}" data-fid="${fm.id}"><span class="fs-dot"></span>${fm.label}</button>`;
      }).join('');

      const entry = pick.entry_low != null ? `$${pick.entry_low}–$${pick.entry_high}` : '';
      const stop  = pick.stop != null ? ` · Stop $${pick.stop}` : '';
      const summary = `<span class="fs-pick-label"><strong style="color:${dirColor}">${dirLabel}</strong> · ${pick.ticker} · ${setupName}${entry ? ' · ' + entry : ''}${stop}</span>`;

      this.el.innerHTML = `<div class="fs-wrap"><div class="fs-top">${dotsHtml}<span class="fs-sep"></span>${summary}</div><div class="fs-detail" id="fs-det"></div></div>`;

      // Wire clicks
      const slot = this.el.parentElement || this.el;
      this.el.querySelectorAll('.fs-dot-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const fid = btn.dataset.fid;
          const det = this.el.querySelector('#fs-det');
          if (this._expanded === fid) {
            this._expanded = null;
            slot.classList.remove('expanded');
            if (det) det.innerHTML = '';
            this.el.querySelectorAll('.fs-dot-btn').forEach(b => b.classList.remove('expanded'));
          } else {
            this._expanded = fid;
            slot.classList.add('expanded');
            this.el.querySelectorAll('.fs-dot-btn').forEach(b => b.classList.toggle('expanded', b.dataset.fid === fid));
            if (det) det.innerHTML = renderChecklist(fid, factors[fid] || {});
          }
        });
      });

      // Pre-fill TA checklist when technical factor fires — det has content
      // without expanding the slot, so the strip stays collapsed until user clicks.
      if (pick && factors.technical?.firing) {
        const det = this.el.querySelector('#fs-det');
        if (det && !det.innerHTML) {
          det.innerHTML = renderChecklist('technical', factors.technical || {});
        }
      }
    }

    unmount() {
      super.unmount();
    }

    resize() {}
  }

  FactorStripModule.id = 'factor-strip';
  FactorStripModule.label = 'Factor Strip';
  FactorStripModule.defaultSize = 'M';
  FactorStripModule.supportedSizes = ['M', 'L'];

  if (window.EV?.registry) window.EV.registry.register(FactorStripModule);
  window.FactorStripModule = FactorStripModule;
})();
