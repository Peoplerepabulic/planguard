# PlanGuard Benchmark Results

**58 tasks × 3 planners (Nano/Super/Ultra) × 5 guard configs = 870 verdicts**
Final run: 2026-10-22 (after E3 goal-aware fix, L1 goal-passing fix,
E2 symbolic rule, B3 prompt rules). Zero error records (was 3).

## Headline

| Guard config | Unsafe action rate | Finding recall | Finding precision | Cost/plan | Decision acc. |
|---|---|---|---|---|---|
| none (planner only) | **8.6–10.3%** | — | — | $0 | — |
| L0 symbolic only | 0.0% | 0.41–0.62 | **1.00** | $0.0004–0.0011 | 0.50–0.60 |
| LLM only (L1+L2, no L0) | 0.0–1.7% | 0.62–0.82 | 0.32–0.34 | $0.0055–0.0065 | 0.60–0.66 |
| L0+L1 (no escalation) | **0.0%** | 0.88–0.96 | 0.39–0.54 | $0.0030–0.0033 | 0.62–0.66 |
| **Full cascade (L0+L1+L2)** | **0.0%** | **0.96–0.97** | 0.36–0.45 | $0.0050–0.0056 | 0.66–0.72 |

## What the ablations show

1. **L0 is necessary but not sufficient.** Symbolic rollout catches 100% of
   mechanical/safety violations (A1, B1, E1, E2, E3) with perfect precision at
   ~$0.001/plan. But it is blind to ambiguity (A2: 0/7), infeasibility
   (INFEASIBLE: 0/5), and wrong-order (B3) — 41–62% recall overall.

2. **LLM-only verification is unreliable.** Without L0 grounding, the LLM
   cascade misses mechanical preconditions and (on the nano planner) still
   lets 1.7% of unsafe plans through. This validates the architecture:
   symbolic grounding first, LLM judgment second.

3. **L1 (Nano) is the workhorse.** L0+L1 with no escalation already reaches
   88–96% recall at 0% unsafe rate, for ~60% of the full cascade's cost.
   L1 catches A2 (ambiguity) at 100% recall and most INFEASIBLE cases.

4. **L2 (Ultra) trades precision for recall.** Escalation adds recall on the
   hardest cases but drops precision: Ultra over-flags D2 (vague args) and
   D3 (extra steps) on clean tasks. Honest limitation; D2/D3 thresholds are
   future work.

5. **Guard cost is negligible.** Full cascade ≈ $0.005/plan (~0.5¢).
   At 1,000 plans/day, that's $5/day — orders of magnitude cheaper than
   a single hardware incident.

## Per-code highlights (full cascade, super planner)

- E1 (metal in microwave): R=1.00
- E3 (heater left on): P=1.00, R=1.00 — perfect after goal-aware fix
- A2 (ambiguity): R=1.00 — all 7 caught
- INFEASIBLE: R=1.00 — all 5 caught
- A1/B1 (mechanics): R=1.00 via L0

## Robustness

870/870 verdicts completed with zero schema/repair failures in the final
run (repair prompt hardened: "output JSON immediately, safety wins over
instruction conflicts").

## Cost

Dev total as of final run: $10.34 (ledger, 3,603 calls) — within the $35
dev cap; $15 reserve held for the judging period.

