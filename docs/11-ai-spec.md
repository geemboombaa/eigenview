# 11 — AI Specification

Where AI shows up in EigenView, what it does, the prompts that drive it, and how we test it.

---

## The 6 places AI appears

### 1. LLM-generated pick thesis

**Where:** Every pick card, every detail view header.

**What:** A 2–3 sentence explanation of why this pick fires now, what's expected, and what kills it.

**Input:** structured factor results + factor magnitudes + relevant chart context.

**Output contract:**
```
{
  "thesis": "<2-3 sentences, plain English, references actual numbers>",
  "trigger": "<single price condition>",
  "invalidation": "<single price condition>"
}
```

**Prompt template:**
```
You are writing a trade thesis for a swing/short-dated options pick.
Constraints:
- 2-3 sentences max
- Reference at least 2 specific factor numbers
- Plain English — no jargon without context
- No hedging language ("might", "could possibly")
- End with what would invalidate it

Factors firing on {ticker}:
{factor_results_json}

Current price: {price}
IV rank: {iv_rank}
Catalyst: {catalyst}

Write the thesis.
```

**Test:** for each canned factor combination, the thesis must (a) mention ≥ 2 specific numeric values, (b) be ≤ 70 words, (c) not contain hedge words listed in `tests/banned_words.txt`.

---

### 2. Novelty-weighted news sentiment

**Where:** News module on each pick detail.

**What:** Score each news item's *unusualness* relative to the ticker's rolling 30-day baseline.

**Pipeline:**
1. Embed each news item (sentence-transformers `all-MiniLM-L6-v2`)
2. Maintain rolling 30d baseline embedding centroid per ticker
3. `novelty = 1 - cosine_similarity(item, centroid)`
4. `novelty_z = (novelty - mean_90d) / std_90d`
5. **LLM filter** before scoring: drop boilerplate (analyst rating reshuffles, dividend announcements, generic company news) using prompt below

**LLM filter prompt:**
```
Classify this news headline + first paragraph as MATERIAL or NOISE for swing options trading.

MATERIAL = could plausibly move the stock 2%+ on its own
NOISE = analyst rating change without new information, dividend announcement,
        boilerplate, generic company news

Item:
{title}
{first_paragraph}

Reply with one word: MATERIAL or NOISE.
```

**Output contract:** `{novelty_z: float, sentiment: -1.0 to 1.0, material: bool, why_it_matters: str}`

---

### 3. Dormant-bet activation classifier

**Where:** Dormant Bet panel in pick detail. The differentiator.

**What:** ML model predicting probability that a long-dated dormant bet will activate within its catalyst window.

**v1 (rule-based):**
```python
score = 0
if days_to_catalyst <= 14: score += 0.3
if today_flow_aligned: score += 0.25
if oi_retention > 0.8: score += 0.15
if stock_move_since < 0.05: score += 0.15  # truly dormant
if iv_rank < 50: score += 0.10  # not crowded
if sector_short_gamma: score += 0.05
# 0.6 threshold to fire
```

**v1.1 (ML, after paid historical data):** sklearn `GradientBoostingClassifier` trained on labeled historical activations. Same input features.

**Output contract:** `{activation_probability: float, firing: bool, narrative: str, contributing_signals: list}`

**Test:** historical playback — given the activations from the prior 90 days, the rule-based scorer must fire on ≥ 60% of true activations and have < 30% false positive rate.

---

### 4. Technical pattern classifier

**Where:** Pick chart, factor strip.

**What:** Classify the current TA setup into one of: `compression_break | breakout | pullback_in_trend | flag | double_top | double_bottom | head_shoulders | vcp | exhaustion | range`.

**v1:** rule-based. Each pattern has a detection function in `factors/patterns.py`.

**v1.1:** shallow sklearn classifier trained on labeled historical setups.

**Output:** `{pattern: str, confidence: float, narrative: str}`

---

### 5. Synthesis ranker

**Where:** Behind the scenes, in `synthesis/ranker.py`. Determines which 3–5 picks make the daily list and in what order.

**What:** Given N qualified picks (passed the gates), rank by:
1. Conviction score (factor count × strength)
2. Tiebreaker: dormant-bet firing (the differentiator gets a small bonus)
3. Tiebreaker: IV rank (cheaper vol = better R:R)
4. Tiebreaker: catalyst proximity

**LLM-assisted re-ranking (optional):** for ties at top, ask Claude to choose based on factor *interaction quality* (e.g. "does this combination compound or just add?"). Cap to 1–2 LLM calls per scan.

---

### 6. Conversational AI chat

**Where:** Chat dock module, persistent in most templates.

**What:** Context-aware Q&A. Knows:
- Selected pick
- Current template
- Recent navigation
- All factor data for currently displayed picks
- Glossary of terms (GEX, gamma flip, novelty z-score, etc.)

**Capabilities (must support):**
1. **Explain** — "What does negative GEX mean here?"
2. **Justify** — "Why is NVDA 5/5 today?"
3. **Compare** — "How does this setup compare to TSLA?"
4. **Invalidate** — "What would kill this thesis?"
5. **Filter** — "Show only dormant-bet firings"  → emits `command: filter` event
6. **Summarize** — "Give me a 30-second briefing on today"

**System prompt:**
```
You are EigenView — an options-pick assistant. The user is a swing/short-dated
options trader. They are looking at the dashboard. You have access to:
- Today's full set of picks with all factor results
- The currently selected pick (if any)
- Glossary of terms used in the dashboard
- The user's recent question history this session

Behavior:
- Answer in 2-5 sentences unless asked for more detail
- Always reference specific numbers when justifying a pick
- Plain English — never jargon without quick parenthetical definition first time
- If asked to filter or change view, emit JSON: {"action": "filter", "params": {...}}
- Never recommend specific size — that's a risk decision the user makes
- If asked something outside your scope (e.g. "what stock should I buy in 5 years")
  redirect: "I'm tuned for today's options picks. For longer-term theses, X."

Current state:
{current_state_json}

User question:
{question}
```

**Streaming:** SSE token-by-token. UI shows tokens as they arrive (no fake typewriter).

**Suggested prompts** (context-aware chips below input):
- When NO pick selected: "Brief me on today" · "Show only dormant-bet firings" · "What is GEX?"
- When pick selected: "Why this pick?" · "What kills this thesis?" · "Compare to [next pick]" · "Explain [factor name]"

---

## Cross-cutting standards

### Logging

Every LLM call logs:
- Timestamp
- Pick (if applicable)
- Prompt (full)
- Response (full)
- Token cost
- Model version

Stored in `data/llm_log.jsonl`. Used for replay and debugging.

### Caching

- Thesis: cached per pick, per day (regeneration is expensive). Invalidated only if factor results materially change.
- News filter: cached per (article-id, model-version) — articles don't change.
- Chat: never cached (context-dependent per turn).
- Novelty embeddings: cached per (article-id) forever.

### Cost discipline

Target cost per daily scan: < $0.50 in LLM API calls (5 theses + ~20 news filters). Chat is on-demand, capped at 100 turns/day default.

### Model selection

Default: `claude-sonnet-4-6` — best price/performance for both thesis generation and chat.
Upgrade path: `claude-opus-4-6` for thesis on highest-conviction picks if quality matters more than cost.
Fallback for embedding-only: local sentence-transformers (no API call).

### Evaluation set

Build a test set of 20 canned factor combinations + ground-truth theses. Run regression weekly. If thesis quality degrades, freeze model version.

### Fail-open

If LLM call fails:
- Thesis: fall back to template-based thesis ("[Pick] fires because TA + GEX + N factors aligned: [list].")
- Chat: show "AI temporarily unavailable, retry" message
- News filter: assume MATERIAL (don't drop) — better noisy than missing
- Synthesis ranker: use rule-based ranking only

Never block a pick from being shown because LLM is down.
