# PlanGuard

**A pre-execution safety runtime that catches LLM robot-planner failures before they reach the physical world.**

LLM planners hallucinate preconditions, skip steps, misread ambiguous instructions,
and leave stoves on. PlanGuard verifies every plan *before execution* and returns
**approve / repair / reject / ask-human** with evidence-cited findings — for about
half a cent per plan.

Built for the **Nebius × NVIDIA Global AI Hackathon** (Physical AI track).
All models run on **Nebius Token Factory** (Nemotron family).

## Results

58-task benchmark × 3 planners × 5 guard configurations = 870 verdicts
(full write-up: [`bench/results_summary.md`](bench/results_summary.md)):

| Guard | Unsafe rate | Recall | Precision | Cost/plan |
|---|---|---|---|---|
| none (planner only) | 8.6–10.3% | — | — | $0 |
| L0 symbolic only | 0.0% | 0.41–0.62 | 1.00 | ~$0.001 |
| LLM only (no L0) | 0.0–1.7% | 0.62–0.82 | 0.32–0.34 | ~$0.006 |
| L0+L1 | 0.0% | 0.88–0.96 | 0.39–0.54 | ~$0.003 |
| **Full cascade** | **0.0%** | **0.96–0.97** | 0.36–0.45 | **~$0.005** |

Red team (25 adversarial tasks, LLM-generated): **96% intercepted** after fixes.
Vision layer (A3 belief-state mismatches in AI2-THOR): **4/5 caught** — a class of
failure no text-only verifier can see in principle.

## Architecture

```
plan ──► L0 symbolic rollout ──► L1 Nemotron Nano ──► L2 Nemotron Ultra
         (preconditions,          (ambiguity,           (hard cases,
          physics, safety           feasibility,          repair
          rules, ~$0.001)           ordering)             generation)
                                        ▲
              VL perception (Nemotron 3.5 Super VL) compares the real
              camera frame against the believed scene graph (A3)
              Tavily grounding checks real-world facts (units, temps)
```

- **L0 — symbolic rollout.** Simulates the plan against a scene graph: action
  preconditions/effects, physics checks, and safety rules (metal in a running
  microwave, sharp object in a hand-held container, heater left on *unless the
  goal requires it*). Deterministic, perfect precision.
- **L1 — Nemotron 3 Nano (30B).** Catches what symbols can't express: ambiguous
  referents (A2), infeasible goals, wrong ordering (B3), missing steps.
- **L2 — Nemotron 3 Ultra (550B).** Escalation for critical/low-confidence
  findings; generates repaired plans (max 2 rounds, re-verified).
- **Perception — Nemotron 3.5 Super VL.** Compares a live camera frame to the
  believed world state; catches belief-state mismatches (A3).
- **Grounding — Tavily.** Real-world fact checks (e.g. safe cooking
  temperatures) injected into verification.

Failure taxonomy (14 codes) aligned with the Embodied Agent Interface
(NeurIPS 2024), extended with a Safety class (E1–E3) and belief-state class
(A3) that EAI lacks: [`bench/taxonomy.md`](bench/taxonomy.md).

## Quickstart

```bash
pip install .
cp .env.example .env   # add NEBIUS_API_KEY (Token Factory), TAVILY_API_KEY
```

### Python SDK

```python
from planguard.verify import Guard

guard = Guard.default()          # full cascade
verdict = guard.verify(plan, scene, goal=goal)
print(verdict.decision)          # approve | repair | reject | ask_human
for f in verdict.findings:
    print(f.code, f.severity, f.message)
```

### MCP server

PlanGuard exposes `verify_plan` / `repair_plan` as MCP tools, so any agent
framework can gate its planner:

```bash
pip install ".[mcp]"
python -m planguard.mcp_server
```

### Web console

```bash
uvicorn planguard.console:app --port 7860
# Live Verify · recorded THOR episode · benchmark · cost ledger
```

## Layout

- `planguard/` — SDK: `world/` (scene graph, executor, safety rules),
  `verify/` (cascade, L1, L2, VL perception), `llm/` (Token Factory client,
  prompts, cost ledger), `grounding/` (Tavily), `mcp_server.py`, `console.py`
- `bench/` — 58 tasks, 7 scenes, labeler, runner, metrics, results
- `redteam/` — adversarial-task brief, intake runner, report
- `static/` + `data/` — console frontend and its cached demo data

## License

Apache-2.0. See [LICENSE](LICENSE).
