"""Benchmark financial sentiment models on REAL EigenView news headlines.

Decision #1: FinBERT-tone vs distilroberta-financial vs VADER.
Pulls real rows from the news table (no synthetic text). Reports per-headline CPU
latency, label distribution, and pairwise agreement. No mocks, no fake data.
"""
from __future__ import annotations

import sqlite3
import time

N = 80  # headlines to benchmark

con = sqlite3.connect(r"data\eigenview.db")
rows = con.execute(
    "SELECT ticker, headline FROM news WHERE headline IS NOT NULL AND length(headline)>15 "
    "ORDER BY timestamp DESC LIMIT ?", (N,)
).fetchall()
con.close()
texts = [r[1] for r in rows]
print(f"Loaded {len(texts)} real headlines from news table\n")


def run_hf(model_id: str, label_map=None):
    from transformers import pipeline
    t0 = time.time()
    clf = pipeline("text-classification", model=model_id, truncation=True, max_length=128)
    load_s = time.time() - t0
    t1 = time.time()
    out = clf(texts)
    infer_s = time.time() - t1
    labels = [ (label_map or (lambda x: x))(o["label"].lower()) for o in out ]
    dist = {l: labels.count(l) for l in set(labels)}
    print(f"{model_id}")
    print(f"  load {load_s:.1f}s | infer {infer_s:.2f}s total | {infer_s/len(texts)*1000:.0f} ms/headline | dist {dist}")
    return labels


def run_vader():
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    a = SentimentIntensityAnalyzer()
    t1 = time.time()
    labels = []
    for t in texts:
        c = a.polarity_scores(t)["compound"]
        labels.append("positive" if c > 0.05 else "negative" if c < -0.05 else "neutral")
    infer_s = time.time() - t1
    dist = {l: labels.count(l) for l in set(labels)}
    print(f"VADER (lexicon baseline)")
    print(f"  infer {infer_s*1000:.0f}ms total | {infer_s/len(texts)*1000:.1f} ms/headline | dist {dist}")
    return labels


def agree(a, b):
    return sum(1 for x, y in zip(a, b) if x == y) / len(a) * 100


norm = lambda x: {"label_0": "negative", "label_1": "neutral", "label_2": "positive"}.get(x, x)

print("=== FinBERT-tone ===")
finbert = run_hf("yiyanghkust/finbert-tone", norm)
print("\n=== distilroberta financial ===")
distil = run_hf("mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis", norm)
print("\n=== VADER ===")
vader = run_vader()

print("\n=== pairwise agreement ===")
print(f"  FinBERT vs distilroberta : {agree(finbert, distil):.0f}%")
print(f"  FinBERT vs VADER         : {agree(finbert, vader):.0f}%")
print(f"  distilroberta vs VADER   : {agree(distil, vader):.0f}%")
print("\n=== sample (headline -> FinBERT / distil / VADER) ===")
for i in range(min(8, len(texts))):
    print(f"  [{finbert[i][:3]}/{distil[i][:3]}/{vader[i][:3]}] {texts[i][:80]}")
