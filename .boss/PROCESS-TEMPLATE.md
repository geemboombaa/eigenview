# EigenView — Per-Feature Step Tracker
# Copy this file to .boss/CURRENT-STEP.md at the start of every feature (step 5).
# Update after EVERY step completes. Commit with .boss/ docs.

## Feature
<!-- Short name, e.g. "dormant-bet-v2" -->

## GitHub Issue
<!-- #123 -->

## PR
<!-- #124 (DRAFT until step 22) -->

## Branch
<!-- feature/... or fix/... -->

## Tier
<!-- feature (full 29 steps) | fix (lightweight: skip steps 5-14) -->

## Current Step
<!-- Step N — what is happening right now -->

## Next Step
<!-- Step N+1 — what triggers next -->

## Blocked On
<!-- None | "Human must remove gate:awaiting-step21 label" | "Human must approve PR" | etc. -->

## Steps Completed
<!-- 1, 2, 3, ... -->

## Steps Remaining
<!-- N, N+1, ... -->

---

## Step Reference (feature/ tier)

| Step | Phase | Action | Who | Gate? |
|------|-------|--------|-----|-------|
| 1 | Research | User describes need | Human | — |
| 2 | Research | Claude deep research | Claude | — |
| 3 | Research | Claude proposes spec | Claude | — |
| 4 | Research | **Human approves proposal** | Human | MANUAL GATE |
| 5 | Lock Req | Claude writes .boss/ docs | Claude | pre-build-gate exempts .boss/ |
| 6 | Lock Req | pre-build-gate active | Hook | blocks src/ if no PR |
| 7 | Lock Req | Claude creates GitHub issue (GIVEN/THEN ACs) | Claude | — |
| 8 | Lock Req | Claude opens draft PR | Claude | unblocks pre-build-gate |
| 9 | Red Phase | Claude writes test stubs (must fail) | Claude | pre-build-gate: PR open |
| 10 | Red Phase | git commit → pre-commit RED phase | git hook | stubs must fail, no regressions |
| 11 | Red Phase | stop-gate: dirty check → tests | stop-gate | blocks if src/ dirty |
| 12 | Red Phase | auto-push | hook | — |
| 13 | CI Audit | GitHub Actions: AC check + Claude audit | CI | separate machine |
| 14 | CI Audit | AC reference + trivial test check | CI | fails if no AC refs |
| 15 | CI Audit | Issue body AC format check (GIVEN/THEN) | CI | fails if missing |
| 16 | CI Audit | Zero-context Claude API audit | CI | — |
| 17 | CI Audit | Audit posted as PR comment | CI | — |
| 18 | CI Audit | verify-red-phase: set phase:red + gate:awaiting-step21 | CI | blocks implementation |
| 19 | CI Audit | **Human reviews CI audit** | Human | MANUAL GATE |
| 20 | Design | Claude writes .boss/design-review.md | Claude | — |
| 21 | Design | **Human approves: removes gate:awaiting-step21** | Human | MANUAL GATE — removes block |
| 22 | Implement | Implementation begins | Claude | pre-build-gate: no step21 gate |
| 23 | Implement | git commit → pre-commit GREEN phase | git hook | all tests must pass |
| 24 | Implement | stop-gate: dirty check → tests | stop-gate | — |
| 25 | Implement | auto-push → CI full suite | CI | — |
| 26 | Implement | Post-implementation Claude audit | CI | — |
| 27 | Ship | **Human reviews CI, approves PR** | Human | MANUAL GATE |
| 28 | Ship | **Human merges PR** | Human | MANUAL GATE — branch protection |
| 29 | Ship | CI re-runs on master | CI | final verification |
