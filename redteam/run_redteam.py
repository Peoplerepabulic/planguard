"""Red-team intake: run adversarial instructions through planner + Guard.

Usage: python redteam/run_redteam.py redteam/tasks_claude.json [more files...]

Each task: {id, category, scene, instruction, intended_issue, taxonomy_code}
For each: Super generates a plan (cached in runs/plans/), Guard verifies.
Report: per-category interception rate + any misses (valuable bugs).
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "runs"))
import vault_auth  # noqa: F401 (sets NEBIUS_API_KEY)

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import dynamic_credential_entry  # noqa: E402
import os  # noqa: E402

os.environ.setdefault("TAVILY_API_KEY", dynamic_credential_entry("custom.tavily")["surrogate"])

from planguard import Plan, Scene  # noqa: E402
from planguard.llm import Ledger, TokenFactory  # noqa: E402
from planguard.planner import generate  # noqa: E402
from planguard.verify import Guard  # noqa: E402

ROOT = pathlib.Path(__file__).parent.parent
PLANS = ROOT / "runs/plans"
OUT = pathlib.Path(__file__).parent / "results.jsonl"


def load_scene(sid: str) -> Scene:
    return Scene.model_validate(json.loads((ROOT / f"bench/scenes/{sid}.json").read_text()))


def get_plan(tf, planner: str, tid: str, instruction: str, scene: Scene) -> Plan:
    cache = PLANS / f"{planner}_{tid}.json"
    if cache.exists():
        return Plan.model_validate(json.loads(cache.read_text()))
    plan = generate(tf, planner, instruction, scene, goal=None)
    cache.write_text(plan.model_dump_json())
    return plan


def main(files):
    tf = TokenFactory(Ledger())
    guard = Guard(tf)
    done = set()
    if OUT.exists():
        done = {json.loads(l)["id"] for l in OUT.open()}
    tasks = []
    for f in files:
        tasks += json.loads(pathlib.Path(f).read_text())
    print(f"{len(tasks)} tasks, {len(done)} already done")
    with OUT.open("a") as fh:
        for t in tasks:
            if t["id"] in done:
                continue
            scene = load_scene(t["scene"])
            try:
                plan = get_plan(tf, "super", t["id"], t["instruction"], scene)
                before = tf.ledger.cost
                v = guard.verify(plan, scene, None)
                codes = {f.code for f in v.findings}
                caught = t.get("taxonomy_code") in codes if t.get("taxonomy_code") else None
                rec = {
                    "id": t["id"], "category": t["category"], "scene": t["scene"],
                    "instruction": t["instruction"], "intended_issue": t.get("intended_issue"),
                    "taxonomy_code": t.get("taxonomy_code"),
                    "decision": v.decision, "findings": [f.model_dump(mode="json") for f in v.findings],
                    "caught_intended": caught, "cost_usd": tf.ledger.cost - before,
                    "n_steps": len(plan.steps),
                }
            except Exception as e:
                rec = {"id": t["id"], "category": t.get("category"), "error": f"{type(e).__name__}: {e}"}
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            verdict = rec.get("decision", "ERROR")
            print(f"  {t['id']}: {verdict} caught={rec.get('caught_intended')}")

    # summary
    recs = [json.loads(l) for l in OUT.open()]
    from collections import defaultdict
    by_cat = defaultdict(lambda: [0, 0, 0])  # caught, missed, other
    misses = []
    for r in recs:
        if r.get("error"):
            continue
        c = by_cat[r["category"]]
        if r["caught_intended"] is True:
            c[0] += 1
        elif r["caught_intended"] is False:
            c[1] += 1
            misses.append(r)
        else:
            c[2] += 1
    print("\n=== red-team summary ===")
    for cat, (a, b, o) in sorted(by_cat.items()):
        print(f"  {cat:12s} caught={a} missed={b} n/a={o}")
    if misses:
        print("\nMISSES (valuable — guard failed to flag the intended issue):")
        for m in misses:
            print(f"  {m['id']}: {m['instruction'][:70]}")
            print(f"     intended={m['taxonomy_code']}, guard found={[f['code'] for f in m['findings']]}")


if __name__ == "__main__":
    main(sys.argv[1:])
