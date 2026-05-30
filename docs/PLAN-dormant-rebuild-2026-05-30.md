# Dormant pipeline rebuild — 2026-05-30 (approved, executing)

Branch: feature/pick-quality-fixes

## Decisions (user-approved)
- Tighten screen: `dormant_size_filter_pct` 0.80→0.98 (top 2%), `dormant_tradeability_dwoi` 1M→10M. Sweep showed loose=18,443 contracts; top2%+$10M=1,426.
- Replace ±3-strike `isolation_multiplier` with `bet_confidence` (multiplicative penalties): V/OI newness, wide same-side vertical scan, cross-expiry calendar scan, risk-reversal, whole-chain balance. Keep if conf ≥ 0.40. Wire into LIVE path at watchlist-write.
- Kill dead branch: `score_dormant`, `score_bet_v2`, `isolation_multiplier`, `_candidate_row`, `_has_catalyst_near`, unused consts. Fix stale docstring on `score_dormant_from_history`.
- Dedup: DormantBet unique key ("ticker","contract") (was 3-col incl original_date). original_date = first-seen (preserved on conflict). Purge legacy dormant_bets (593-ticker, 73k rows) — derived, rebuilt by scan.
- Backfill bug: replace global-max window with per-contract 180d (group symbols by per-symbol max history date; no-history→today-180d, existing→incremental tail). on_conflict_do_nothing. Watchlist is 184-only (write only runs for in_options).
- Keep contract_history (paid Jan–May data); backfill only fills gaps.

## Execution order
1. [ ] config.py: tighten + hedge knobs
2. [ ] dormant.py: add bet_confidence (TDD), remove dead branch, fix docstring
3. [ ] storage.py: DormantBet 2-col unique constraint
4. [ ] scanner.py: bet_confidence gate at write, 2-col upsert, per-contract 180d backfill
5. [ ] tests: rewrite test_dormant_scoring.py (bet_confidence), trim test_dormant_score_db.py (drop score_dormant)
6. [ ] delete dead scratch scripts importing killed symbols
7. [ ] full pytest green; semgrep audit clean
8. [ ] purge legacy dormant_bets; rebuild tightened watchlist from stored 2026-05-29 chains (no download)
9. [ ] estimate_cost on new symbols → pull missing 180d
10. [ ] scan download=False → picks → restart UI → verify
11. [ ] commit + push + PR
12. [ ] propose walk-forward data-pull strategy
