(() => {
  const CSS_ID = 'ev-help-css';
  const CSS = `
#ev-help-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 32px 16px;
  overflow-y: auto;
}
#ev-help-overlay[hidden] { display: none; }
.ev-help-box {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 12px;
  width: 100%;
  max-width: 860px;
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 90vh;
}
.ev-help-head {
  display: flex;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  gap: 12px;
}
.ev-help-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
  flex: 1;
  letter-spacing: 0.5px;
}
.ev-help-close {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 5px;
  color: var(--text-dim);
  cursor: pointer;
  font-size: 13px;
  padding: 4px 10px;
}
.ev-help-close:hover { color: var(--text); }
.ev-help-tabs {
  display: flex;
  gap: 2px;
  padding: 8px 16px 0;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  overflow-x: auto;
}
.ev-help-tab {
  font-size: 11px;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  font-weight: 600;
  padding: 6px 14px;
  border-radius: 6px 6px 0 0;
  border: 1px solid transparent;
  border-bottom: none;
  cursor: pointer;
  color: var(--text-dim);
  background: transparent;
  white-space: nowrap;
  margin-bottom: -1px;
}
.ev-help-tab.active {
  color: var(--text);
  background: var(--panel);
  border-color: var(--border);
  border-bottom-color: var(--panel);
}
.ev-help-tab:hover:not(.active) { color: var(--text); background: var(--panel-2); }
.ev-help-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px 24px 32px;
}
.ev-help-panel { display: none; }
.ev-help-panel.active { display: block; }
.ev-help-section {
  margin-bottom: 28px;
}
.ev-help-section-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.ev-help-section-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
  text-transform: uppercase;
  letter-spacing: 1px;
}
.ev-help-live-badge {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 1px;
  padding: 2px 7px;
  border-radius: 3px;
  text-transform: uppercase;
}
.ev-help-live-badge.live { background: var(--accent); color: #000; }
.ev-help-live-badge.partial { background: var(--warn); color: #000; }
.ev-help-live-badge.stub { background: var(--border); color: var(--text-dim); }
.ev-help-p {
  font-size: 12px;
  line-height: 1.7;
  color: var(--text-dim);
  margin-bottom: 8px;
}
.ev-help-p strong { color: var(--text); font-weight: 600; }
.ev-help-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.ev-help-chip {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid var(--chip-border);
  background: var(--chip-bg);
  color: var(--text-dim);
  font-weight: 600;
}
.ev-help-divider {
  border: none;
  border-top: 1px solid var(--border-soft);
  margin: 20px 0;
}
.ev-help-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
  margin-top: 8px;
}
.ev-help-table th {
  text-align: left;
  color: var(--text-faint);
  font-weight: 600;
  letter-spacing: 0.5px;
  padding: 4px 8px;
  border-bottom: 1px solid var(--border);
}
.ev-help-table td {
  padding: 5px 8px;
  color: var(--text-dim);
  border-bottom: 1px solid var(--border-soft);
  vertical-align: top;
}
.ev-help-table td:first-child { color: var(--text); font-weight: 600; white-space: nowrap; }
.ev-help-callout {
  background: var(--panel-2);
  border-left: 3px solid var(--accent);
  padding: 10px 14px;
  border-radius: 0 6px 6px 0;
  margin: 12px 0;
  font-size: 12px;
  color: var(--text-dim);
  line-height: 1.6;
}
.ev-help-callout strong { color: var(--accent); }
`;

  function injectCSS() {
    if (document.getElementById(CSS_ID)) return;
    const s = document.createElement('style');
    s.id = CSS_ID;
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  const TABS = [
    { id: 'overview', label: 'Overview' },
    { id: 'ta', label: 'Technical' },
    { id: 'gex', label: 'GEX' },
    { id: 'flow', label: 'Flow' },
    { id: 'dormant', label: 'Dormant Bet' },
    { id: 'sentiment', label: 'Sentiment' },
    { id: 'macro', label: 'Macro' },
    { id: 'selection', label: 'Stock Selection' },
    { id: 'ui', label: 'Dashboard UI' },
  ];

  const PANELS = {
    overview: `
      <div class="ev-help-section" id="help-overview">
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">What is EigenView?</span>
        </div>
        <p class="ev-help-p">EigenView is a <strong>daily options-intelligence dashboard</strong> that produces 3–5 curated, high-conviction trade ideas each morning by fusing 5 independent signal layers that no single existing product combines.</p>
        <p class="ev-help-p">Every pick requires <strong>Technical Analysis AND GEX</strong> to fire (hard gates). Then at least 2 of 3 soft signals — Flow, Dormant Bet, Sentiment — must align. If those criteria aren't met, the stock stays on the watchlist, not the picks list.</p>
        <div class="ev-help-callout">
          <strong>Gate logic:</strong> TA ✓ + GEX ✓ + (Flow OR Dormant OR Sentiment — 2 of 3) → Pick<br/>
          Fail any hard gate = no pick, regardless of other signals.
        </div>
        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">The 5 Signal Layers</span>
        </div>
        <table class="ev-help-table">
          <thead><tr><th>Signal</th><th>What it measures</th><th>Status</th></tr></thead>
          <tbody>
            <tr><td>Technical Analysis</td><td>Trend, momentum, pattern, volatility state</td><td><span class="ev-help-live-badge live">Live</span></td></tr>
            <tr><td>GEX / Dealer Positioning</td><td>Gamma exposure, call/put walls, gamma flip</td><td><span class="ev-help-live-badge live">Live</span></td></tr>
            <tr><td>Options Flow</td><td>Fresh OI, aggressive premium, skew shift</td><td><span class="ev-help-live-badge live">Live</span></td></tr>
            <tr><td>Dormant-Bet Radar</td><td>Large long-dated positions activating (ML)</td><td><span class="ev-help-live-badge partial">Partial</span></td></tr>
            <tr><td>Catalyst + Sentiment</td><td>LLM novelty scoring vs. rolling baseline</td><td><span class="ev-help-live-badge live">Live</span></td></tr>
          </tbody>
        </table>
      </div>
    `,

    ta: `
      <div class="ev-help-section" id="help-ta">
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Technical Analysis</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">Technical analysis scores each ticker across 4 sub-dimensions: <strong>trend, momentum, volatility state,</strong> and <strong>ML pattern classification</strong>. A composite TA score must cross a minimum threshold for the TA gate to fire.</p>
        <hr class="ev-help-divider"/>

        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Trend</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">Uses <strong>EMA 21 vs EMA 50</strong>: price above both = bullish trend (+1), below both = bearish (–1), between = neutral (0). Slope of the 50-period EMA adds acceleration weighting.</p>
        <div class="ev-help-chips"><span class="ev-help-chip">EMA 21</span><span class="ev-help-chip">EMA 50</span><span class="ev-help-chip">Slope</span></div>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Momentum (RSI + MACD)</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p"><strong>RSI(14)</strong> scores: above 55 = bullish (+1), below 45 = bearish (–1). <strong>MACD histogram</strong> crossing zero line adds confirmation. Divergence between price and RSI is flagged but not gated.</p>
        <div class="ev-help-chips"><span class="ev-help-chip">RSI 14</span><span class="ev-help-chip">MACD</span><span class="ev-help-chip">Histogram</span></div>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Volatility State (Bollinger Bands)</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p"><strong>Bollinger Band width</strong> classifies the stock as expanding (breakout candidate), contracting (compression), or normal. Breakouts from compression get a bonus score. Price touching bands is noted as extended.</p>
        <div class="ev-help-chips"><span class="ev-help-chip">BB Width</span><span class="ev-help-chip">BB Upper</span><span class="ev-help-chip">BB Lower</span></div>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">ML Pattern Classification</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">A scikit-learn classifier trained on labeled candle sequences identifies 4 patterns: <strong>Breakout ↑</strong>, <strong>Pullback in trend</strong>, <strong>Compression Break</strong>, and <strong>Bearish Reversal ↓</strong>. Confidence score shown on chart badge.</p>
        <div class="ev-help-chips">
          <span class="ev-help-chip">Breakout ↑</span>
          <span class="ev-help-chip">Pullback</span>
          <span class="ev-help-chip">Compression Break</span>
          <span class="ev-help-chip">Bearish ↓</span>
        </div>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Key Levels</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">Support and resistance levels computed from swing highs/lows over the trailing 20 bars. Used to define entry zone (near support for longs) and stop level (below prior swing low).</p>
      </div>
    `,

    gex: `
      <div class="ev-help-section" id="help-gex">
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">GEX — Gamma Exposure</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">Gamma Exposure (GEX) measures how much market makers must buy or sell stock to stay delta-neutral as price moves. Positive GEX suppresses moves; negative GEX amplifies them. EigenView uses per-strike GEX to find structural price levels.</p>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Call Wall</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">Strike with the highest positive GEX on the call side. Price tends to <strong>stall or reverse</strong> at this level as dealers sell into rallies to stay hedged. Shown as a green dashed line on the price chart.</p>
        <div class="ev-help-chips"><span class="ev-help-chip">Call Wall</span></div>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Put Wall</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">Strike with the highest put GEX. Acts as a <strong>price magnet or support floor</strong> — dealers buy stock as price falls to this level. Shown as a red dashed line.</p>
        <div class="ev-help-chips"><span class="ev-help-chip">Put Wall</span></div>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Gamma Flip Level</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">The price at which total GEX crosses zero — from positive (stabilizing) to negative (amplifying). <strong>Below flip = dealers add fuel to moves</strong> (sell rallies AND sell dips, trending). Above flip = mean reversion regime. Shown as amber solid line.</p>
        <div class="ev-help-chips"><span class="ev-help-chip">Gamma Flip</span><span class="ev-help-chip">GEX Regime</span></div>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">GEX Gate Condition</span>
        </div>
        <p class="ev-help-p">GEX fires bullish when: price is <strong>above gamma flip</strong> AND in positive GEX regime AND call wall is meaningfully above current price (room to run). Bearish when price is below flip in negative regime with put wall nearby.</p>
      </div>
    `,

    flow: `
      <div class="ev-help-section" id="help-flow">
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Options Flow Quality</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">Flow measures whether the options market shows <strong>informed, directional conviction</strong> — not just noise volume. EigenView scores 4 flow dimensions and requires a composite above threshold for the flow soft gate.</p>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Fresh OI Build</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">Open Interest that didn't exist in yesterday's chain is "fresh." Large fresh OI at a specific strike signals someone <strong>newly committed capital</strong> — not rolling, not closing. Rolled or hedged flow scores zero.</p>
        <div class="ev-help-chips"><span class="ev-help-chip">OI Delta</span><span class="ev-help-chip">Fresh OI</span></div>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Aggressive Side</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">Distinguishes buyers from sellers using <strong>ask-side vs. bid-side fills</strong>. Transactions at or above ask = buyers paying up. Transactions at or below bid = sellers dumping. Ask-side premium = bullish urgency.</p>
        <div class="ev-help-chips"><span class="ev-help-chip">Ask-side</span><span class="ev-help-chip">Bid-side</span></div>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Premium Size</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">Total dollar premium of directional flow, normalized by average daily volume. Small premium in large volume = noise. Large premium (>$250K ask-side) in targeted strike = signal. Whale threshold: $1M+.</p>
        <div class="ev-help-chips"><span class="ev-help-chip">Premium $</span><span class="ev-help-chip">Whale</span></div>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Skew Shift</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">Change in implied volatility skew between put strikes and call strikes at equivalent deltas. Sudden call-skew steepening signals <strong>demand for upside protection</strong> — a leading indicator of directional commitment.</p>
        <div class="ev-help-chips"><span class="ev-help-chip">IV Skew</span><span class="ev-help-chip">Put-Call Skew</span></div>
      </div>
    `,

    dormant: `
      <div class="ev-help-section" id="help-dormant">
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Dormant-Bet Radar</span>
          <span class="ev-help-live-badge partial">Partial — ML v1 stub</span>
        </div>
        <div class="ev-help-callout">
          <strong>This is EigenView's moat.</strong> No competitor does this. Dormant-bet radar detects large long-dated positions that were placed weeks or months ago and are now <em>activating</em> — showing delta accumulation, rising IV, or early exercise signals.
        </div>
        <p class="ev-help-p">A dormant bet is a long-dated call or put block (typically 60–180 DTE) placed when the stock was quiet, now showing signs of the thesis playing out. These often precede big moves by days.</p>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Detection Method</span>
          <span class="ev-help-live-badge partial">Partial</span>
        </div>
        <p class="ev-help-p">EigenView tracks OI in strikes 60+ DTE across weekly snapshots. When a block of OI that has been static for 2+ weeks suddenly shows volume activity <strong>without fresh OI</strong> (meaning existing holders are trading), the ML classifier scores it as activating.</p>
        <div class="ev-help-chips"><span class="ev-help-chip">OI Age</span><span class="ev-help-chip">DTE ≥ 60</span><span class="ev-help-chip">Volume on static OI</span><span class="ev-help-chip">Delta accumulation</span></div>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">ML Classifier</span>
          <span class="ev-help-live-badge stub">Stub — training pending</span>
        </div>
        <p class="ev-help-p">A scikit-learn gradient-boosted classifier trained on historical dormant-bet examples. Features: OI age, block size, DTE, delta, IV change, volume/OI ratio. Currently returns heuristic score pending full training data.</p>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">What activating looks like</span>
        </div>
        <p class="ev-help-p">Signals of activation: static OI block shows 3x+ normal volume, IV on those strikes rises while other strikes stay flat, delta of block shifts (gamma exposure building), news event or earnings approaching.</p>
      </div>
    `,

    sentiment: `
      <div class="ev-help-section" id="help-sentiment">
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Catalyst + Novelty Sentiment</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">EigenView doesn't score raw news volume — it scores <strong>novelty</strong>: how unusual is today's news relative to this ticker's historical baseline? Novel catalysts carry more signal weight than routine coverage.</p>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">FinBERT Sentiment</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">Each news headline is scored by <strong>FinBERT</strong>, a finance-tuned BERT model, for positive/negative/neutral sentiment. Raw sentiment alone is noisy — it's weighted by novelty score.</p>
        <div class="ev-help-chips"><span class="ev-help-chip">FinBERT</span><span class="ev-help-chip">Positive</span><span class="ev-help-chip">Negative</span><span class="ev-help-chip">Neutral</span></div>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Novelty Scoring</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">News is embedded using a sentence-transformer model. Cosine similarity against a 30-day rolling embedding baseline for that ticker determines novelty. Low similarity = unusual = high weight. High similarity = same old news = low weight.</p>
        <div class="ev-help-chips"><span class="ev-help-chip">Embedding</span><span class="ev-help-chip">Cosine similarity</span><span class="ev-help-chip">Rolling baseline</span></div>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Catalyst Types</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">EigenView identifies catalyst categories from news: earnings surprise, FDA approval/rejection, analyst upgrade/downgrade, M&A rumor, macro event, regulatory action. Hard catalyst events (earnings, FDA) get a fixed score bonus.</p>
        <div class="ev-help-chips">
          <span class="ev-help-chip">Earnings</span>
          <span class="ev-help-chip">FDA</span>
          <span class="ev-help-chip">M&amp;A</span>
          <span class="ev-help-chip">Analyst</span>
          <span class="ev-help-chip">Regulatory</span>
        </div>
      </div>
    `,

    macro: `
      <div class="ev-help-section" id="help-macro">
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Macro Regime</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">The macro panel shows <strong>market-wide regime signals</strong> that set context for every pick. EigenView does not gate picks on macro, but macro regime is shown prominently so you can size and direction-bias accordingly.</p>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">VIX Term Structure</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p"><strong>VIX M1/M2/M3</strong> contango vs. backwardation. Contango (M1 &lt; M2 &lt; M3) = calm, options sellers favored. Backwardation (M1 &gt; M2) = fear elevated, directional options buyers favored. Contango % shown in market context bar.</p>
        <div class="ev-help-chips"><span class="ev-help-chip">VIX M1</span><span class="ev-help-chip">VIX M2</span><span class="ev-help-chip">VIX M3</span><span class="ev-help-chip">Contango %</span></div>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">DIX — Dealer Implied eXposure</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">DIX measures dark-pool buying pressure. High DIX (>45%) signals <strong>institutional accumulation in dark pools</strong> — often a leading indicator of S&amp;P rally. Low DIX = distribution. Shows the smart money's hand before it hits lit markets.</p>
        <div class="ev-help-chips"><span class="ev-help-chip">DIX %</span><span class="ev-help-chip">Dark pool</span></div>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Market GEX Index</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">Aggregate SPX gamma exposure. Positive = suppressed vol, mean-reversion regime. Negative = amplified vol, trending regime. Combined with VIX term structure to classify overall market as <strong>Trending / Ranging / Volatile</strong>.</p>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">COT — Commitment of Traders</span>
          <span class="ev-help-live-badge live">Live</span>
        </div>
        <p class="ev-help-p">CFTC weekly report showing <strong>net long/short positioning of large speculators</strong> in ES futures (S&amp;P proxy). Extreme net-long = complacency risk. Extreme net-short = potential squeeze fuel. Updated weekly.</p>
        <div class="ev-help-chips"><span class="ev-help-chip">COT Net Long %</span><span class="ev-help-chip">ES Futures</span></div>
      </div>
    `,

    selection: `
      <div class="ev-help-section" id="help-selection">
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">How EigenView Selects Stocks</span>
        </div>
        <p class="ev-help-p">EigenView is a <strong>daily batch scanner</strong>, not a real-time feed. Each morning at 8AM, it runs a full pipeline across the configured universe (Nasdaq-100 by default) and stores results to the database. The frontend polls every 5 minutes for freshness.</p>

        <div class="ev-help-callout">
          <strong>Why batch?</strong> yfinance and Finnhub have rate limits. Fetching prices + chains + news for 100 stocks takes ~3-5 minutes. Real-time scanning of 100 tickers continuously isn't feasible on free tiers — and isn't needed for swing/short-dated options where daily setups are the relevant timeframe.
        </div>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Pipeline Steps</span>
        </div>
        <table class="ev-help-table">
          <thead><tr><th>Step</th><th>What happens</th><th>Duration</th></tr></thead>
          <tbody>
            <tr><td>7:45 AM</td><td>Fetch macro signals (VIX, DIX, COT)</td><td>~15s</td></tr>
            <tr><td>8:00 AM</td><td>Daily scan starts — fetch prices, chains, news for each ticker</td><td>~3-5 min</td></tr>
            <tr><td>8:05 AM</td><td>Score all 5 factors per ticker, run gate logic</td><td>~30s</td></tr>
            <tr><td>8:06 AM</td><td>Qualified picks ranked by conviction score, theses generated by LLM</td><td>~1 min</td></tr>
            <tr><td>8:07 AM</td><td>Results stored to DB. Dashboard shows picks.</td><td>—</td></tr>
          </tbody>
        </table>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Universe</span>
          <span class="ev-help-live-badge live">NDX100 configured</span>
        </div>
        <p class="ev-help-p">Default universe: <strong>Nasdaq-100</strong> (~100 US large-cap liquid options stocks). All have tight spreads and adequate daily options volume for reliable flow data. You can override with <code>eigenview daily-scan --universe test5</code> for a 5-stock development run.</p>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Conviction Score</span>
        </div>
        <p class="ev-help-p">Picks are ranked by a 1–5 conviction score. 5 = maximum alignment across all 5 signals. 3 = minimum threshold. Conviction also determines suggested position sizing guidance in the pick thesis.</p>
        <div class="ev-help-chips"><span class="ev-help-chip">Conviction 1–5</span><span class="ev-help-chip">Signal alignment</span><span class="ev-help-chip">Gate pass</span></div>
      </div>
    `,

    ui: `
      <div class="ev-help-section" id="help-ui">
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Dashboard Modules</span>
        </div>
        <table class="ev-help-table">
          <thead><tr><th>Module</th><th>What it shows</th></tr></thead>
          <tbody>
            <tr><td>Market Context</td><td>VIX, DIX, GEX index, regime label, COT positioning</td></tr>
            <tr><td>Pick Cards</td><td>Today's qualified picks — conviction, setup type, thesis summary, signal chips</td></tr>
            <tr><td>Price Chart</td><td>Candlestick chart with EMA21/50, Bollinger Bands, GEX walls, pattern badge</td></tr>
            <tr><td>Factor Strip</td><td>Per-pick breakdown of all 5 factor scores with sub-signal detail</td></tr>
            <tr><td>AI Chat</td><td>Ask anything about picks, signals, or options concepts — powered by Claude</td></tr>
            <tr><td>Category Nav</td><td>Filter picks by setup type — Breakout, Pullback, Compression, etc.</td></tr>
            <tr><td>Voice Orb</td><td>Voice input for AI chat (future)</td></tr>
          </tbody>
        </table>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Keyboard Shortcuts</span>
        </div>
        <table class="ev-help-table">
          <thead><tr><th>Key</th><th>Action</th></tr></thead>
          <tbody>
            <tr><td>T</td><td>Cycle theme (Dark → Light → Glass → Bento)</td></tr>
            <tr><td>E</td><td>Toggle edit mode (drag / resize / close panels)</td></tr>
            <tr><td>1–5</td><td>Switch layout template (Standard / Minimal / Pro / Research / Focus)</td></tr>
            <tr><td>↑ ↓</td><td>Navigate between picks</td></tr>
            <tr><td>/</td><td>Focus AI chat input</td></tr>
            <tr><td>Ctrl+K</td><td>Focus ticker search</td></tr>
            <tr><td>Esc</td><td>Close overlays, blur inputs</td></tr>
            <tr><td>?</td><td>Show keyboard shortcut reference</td></tr>
          </tbody>
        </table>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Edit Mode</span>
        </div>
        <p class="ev-help-p">Press <strong>E</strong> to enter edit mode. Drag panel headers to rearrange, resize from the bottom-right corner handle, click ✕ to close any panel. Click <strong>Done</strong> or press Esc to exit.</p>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Themes</span>
        </div>
        <div class="ev-help-chips">
          <span class="ev-help-chip">Dark — default, deep navy</span>
          <span class="ev-help-chip">Light — white panel</span>
          <span class="ev-help-chip">Glass — frosted Apple</span>
          <span class="ev-help-chip">Bento — high contrast, colored strips</span>
        </div>

        <hr class="ev-help-divider"/>
        <div class="ev-help-section-head">
          <span class="ev-help-section-title">Pick Card Chips</span>
        </div>
        <p class="ev-help-p">Each pick card shows colored chips for each signal that fired. Click any chip to jump to that signal's help section. Green = bullish signal. Red = bearish. Gray = neutral / not fired.</p>
      </div>
    `,
  };

  function buildOverlay() {
    const overlay = document.createElement('div');
    overlay.id = 'ev-help-overlay';
    overlay.hidden = true;
    overlay.innerHTML = `
      <div class="ev-help-box">
        <div class="ev-help-head">
          <span class="ev-help-title">EigenView — Signal & Feature Reference</span>
          <button class="ev-help-close" id="ev-help-close-btn">✕ Close</button>
        </div>
        <div class="ev-help-tabs" id="ev-help-tabs">
          ${TABS.map((t, i) => `<button class="ev-help-tab${i===0?' active':''}" data-tab="${t.id}">${t.label}</button>`).join('')}
        </div>
        <div class="ev-help-body" id="ev-help-body">
          ${TABS.map((t, i) => `<div class="ev-help-panel${i===0?' active':''}" id="ev-help-panel-${t.id}">${PANELS[t.id] || ''}</div>`).join('')}
        </div>
      </div>`;
    document.body.appendChild(overlay);

    overlay.addEventListener('click', e => {
      if (e.target === overlay) overlay.hidden = true;
    });
    document.getElementById('ev-help-close-btn').addEventListener('click', () => {
      overlay.hidden = true;
    });
    document.getElementById('ev-help-tabs').addEventListener('click', e => {
      const tab = e.target.closest('.ev-help-tab');
      if (!tab) return;
      const id = tab.dataset.tab;
      document.querySelectorAll('.ev-help-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === id));
      document.querySelectorAll('.ev-help-panel').forEach(p => p.classList.toggle('active', p.id === `ev-help-panel-${id}`));
    });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && !overlay.hidden) overlay.hidden = true;
    });
  }

  function init() {
    injectCSS();
    buildOverlay();
  }

  window.EV_Help = {
    open(tabId, sectionId) {
      const overlay = document.getElementById('ev-help-overlay');
      if (!overlay) return;
      overlay.hidden = false;
      if (tabId) {
        document.querySelectorAll('.ev-help-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tabId));
        document.querySelectorAll('.ev-help-panel').forEach(p => p.classList.toggle('active', p.id === `ev-help-panel-${tabId}`));
      }
      if (sectionId) {
        requestAnimationFrame(() => {
          const el = document.getElementById(sectionId);
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
      }
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
