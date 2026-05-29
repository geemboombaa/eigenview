# Sentiment / News — research + proposed next steps (NO CODE YET)

Status: research complete, awaiting approval. Companion to `docs/14-data-sources.md`.
Context: today sentiment fires for **0 / 504** tickers. Two causes: (1) news is stale
(pipeline doesn't refresh per scan reliably; AV free = 25/day), (2) the scorer is shallow
(keyword bull/bear word-set counts + catalyst proximity in `factors/sentiment.py`).

## Problem with the current scorer
- `_BULLISH`/`_BEARISH` are ~10-word sets matched against whitespace-split tokens. Misses
  negation ("not strong"), context, finance idiom. Effectively noise.
- Fires only on `catalyst_near OR (≥3 articles AND bull>bear)` → almost never with stale news.
- No real direction confidence, no magnitude.

## Research findings (cited)

**Local finance models**
- **FinBERT (ProsusAI)** — BERT fine-tuned on financial corpus; ~97% on Financial PhraseBank
  high-agreement subset. 110M params. ([HF](https://huggingface.co/ProsusAI/finbert),
  [arXiv 2306.02136](https://arxiv.org/pdf/2306.02136))
- **FinBERT-tone (yiyanghkust)** — fine-tuned on analyst-report sentences; better on financial
  *tone*; gives pos/neg/neutral. ([HF finbert-tone](https://huggingface.co/yiyanghkust/finbert-tone))
- **distilroberta financial-news-sentiment** — DistilRoBERTa, ~2× smaller/faster, small accuracy
  trade-off. Good if CPU-bound.
- **VADER** — lexicon baseline, ~ms latency, no finance tuning. Use as a fallback/sanity only.

**LLMs vs FinBERT (2026 literature)**
- ChatGPT zero-shot **beats** FinBERT on headline→next-day-return alignment ([IEEE CAI 2026 review](https://arxiv.org/html/2605.05211); [arXiv 2602.00086](https://www.arxiv.org/pdf/2602.00086)).
- Fine-tuned LLMs (FinLlama) beat FinBERT by ~44.7% cumulative return ([FinLlama](https://arxiv.org/html/2403.12285v1)).
- **But:** at ~600 names/day × N headlines, per-headline LLM calls = latency + $ cost. Fine-tuning
  needs labeled data we don't have yet.

**Free news sources** ([dev.to 2026 comparison](https://dev.to/nexgendata/best-free-stock-market-apis-and-data-tools-in-2026-a-developers-honest-comparison-1926))
- **Finnhub** — 60 calls/min free (best rate for bulk ~600 names), company news + basic sentiment.
- **Alpha Vantage** — 25/day free, but article+ticker sentiment with direction+magnitude.
- **Marketaux** — 5,000+ sources, directional sentiment, free tier (limited).
- **Tiingo** — clean EOD + news on free tier.

## Reconciliation with CLAUDE.md LLM scope
CLAUDE.md: LLM is **downstream only** (thesis, material/noise filter, chat) — *not* a classifier,
and explicitly *not* worth per-item LLM cost at scan scale. The 2026 results don't overturn that
at our scale (cost/latency over 600 names). So:
- **Direction classification = local model (FinBERT-tone).** Free, fast, batchable, no API cost.
- **Claude stays downstream:** MATERIAL/NOISE filter on the *small set of picks only* (already
  specced in CLAUDE.md, currently unused), + thesis + chat. Consistent, no scope violation.

## Proposed architecture (for approval)

1. **Decouple news from the scan.** A separate scheduled job (`fetch-news`, e.g. Task Scheduler
   pre-market) pulls Finnhub-primary + AV-secondary, dedups by URL hash → `news` table. The scan
   reads whatever news exists (never blocks, never wedges on rate limits). Fixes the "stale news"
   root cause and the 25/day AV ceiling.
2. **Replace the keyword scorer with FinBERT-tone (local).** New `factors/sentiment.py` path:
   - For each ticker's recent headlines (≤3 days), run FinBERT-tone → per-article pos/neg/neutral
     + confidence; aggregate to a direction + strength (confidence-weighted, recency-weighted).
   - Keep catalyst proximity as a *bonus*, not the sole trigger.
   - VADER as a fallback only if the model fails to load.
   - Runs locally (CPU/GPU), batched. **Benchmark before commit** — FinBERT base ~50–150 ms/headline
     single-thread CPU (estimate; must measure on this box); batching + the decoupled job make
     600-name scale fine. (No fabricated number shipped — this is flagged for measurement.)
3. **MATERIAL/NOISE Claude filter on picks only** (downstream, small N) — wire the existing spec.
4. **Novelty embeddings (MiniLM)** — original spec. **Defer to v1.1**: needs a per-ticker 30-day
   baseline to be meaningful; adds a ~80MB model. Not required for sentiment to start firing.

## Does the `≥2 soft factors` gate change?
- **Today:** soft = {flow, dormant, sentiment}; with sentiment dead, only flow+dormant can satisfy
  ≥2 → near-impossible (no ticker hit firing≥4 in the 2026-05-29 scan).
- **Recommendation:** do **not** loosen the gate yet. First make sentiment a *real* firing factor
  (steps 1–2). Re-measure soft-factor co-firing on a fresh scan. **Only if** picks remain
  near-zero with sentiment live do we revisit (options then: ≥2-of-3 with a strength floor, or a
  weighted soft-score ≥ threshold instead of a hard count). Decision deferred to post-measurement —
  no premature tuning.

## Open-source reuse check (don't reinvent — confirmed pip-ready)
Detailed OSS search done. Almost nothing needs custom code — it's assembly:

| Need | Reuse (pip/HF) | Maintained? | Custom work |
|---|---|---|---|
| FinBERT direction | HF `transformers` `pipeline("text-classification", model="yiyanghkust/finbert-tone")` | yes | none — call the pipeline |
| Lexicon fallback | `vaderSentiment` (PyPI) | yes | none |
| Finnhub news | `finnhub-python` (PyPI, v2.4.28 Apr-2026, 60 req/min) | yes | thin wrapper only |
| Alpha Vantage news | `alpha_vantage` / `alphavantage-api-client` (PyPI) | yes | thin wrapper only |
| Novelty embeddings | `sentence-transformers` MiniLM | yes | (deferred v1.1) |
| MATERIAL/NOISE | existing `anthropic` client (already in deps) | yes | prompt only |

**Conclusion:** new code = (a) a scheduled news job around `finnhub-python`, (b) rewrite
`factors/sentiment.py` to call the FinBERT pipeline + aggregate. No model training, no
hand-rolled NLP. Model weights download once (~110MB FinBERT-tone).

## Open decisions (need your call before code)
- [ ] FinBERT-tone vs distilroberta (accuracy vs CPU speed) — benchmark both on this box first?
- [ ] News job cadence: pre-market once, or intraday refresh too?
- [ ] Finnhub as primary (rate) vs Alpha Vantage as primary (richer sentiment)?
- [ ] MiniLM novelty in v1.1 or cut entirely for v1?

Sources: [ProsusAI/finbert](https://huggingface.co/ProsusAI/finbert) · [finbert-tone](https://huggingface.co/yiyanghkust/finbert-tone) · [arXiv 2306.02136](https://arxiv.org/pdf/2306.02136) · [IEEE CAI 2026 LLM review](https://arxiv.org/html/2605.05211) · [Sentiment trading w/ LLMs](https://arxiv.org/pdf/2412.19245) · [FinLlama](https://arxiv.org/html/2403.12285v1) · [Free stock APIs 2026](https://dev.to/nexgendata/best-free-stock-market-apis-and-data-tools-in-2026-a-developers-honest-comparison-1926)
