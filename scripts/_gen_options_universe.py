import os

base = os.path.join(os.path.dirname(__file__), "..")
src = os.path.join(base, "docs", "optionable-watchlist.csv")
out = os.path.join(base, "src", "eigenview", "data", "options_universe.txt")

syms = []
with open(src) as f:
    for i, line in enumerate(f):
        if i < 4:
            continue
        s = line.split(",")[0].strip()
        if not s:
            continue
        if "/" in s:  # BRK/B — Databento can't resolve; dropped per instruction
            continue
        syms.append(s)

syms = sorted(set(syms))
with open(out, "w") as f:
    f.write("\n".join(syms) + "\n")
print(f"wrote {len(syms)} tickers to {out}")
print("dropped slash-names (e.g. BRK/B)")
