"""Parallel benchmark runner with (planner, task) plan caching.

Usage:
    python bench/run.py --planner super --guard full --workers 8
    python bench/run.py --planner nano --guard l0 --tasks bench/tasks.json
"""

import argparse
import json
import os
import pathlib
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

if "NEBIUS_API_KEY" not in os.environ:
    sys.path.insert(0, str(HERE.parent / "runs"))
    import vault_auth  # noqa: F401
    sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
    from dynamic_credentials import dynamic_credential_entry
    os.environ["TAVILY_API_KEY"] = dynamic_credential_entry("custom.tavily")["surrogate"]

from planguard import Plan, Scene  # noqa: E402
from planguard.llm import Ledger, TokenFactory  # noqa: E402
from planguard.planner import generate  # noqa: E402
from planguard.verify import Guard  # noqa: E402

from labeler import label, load_scene, load_tasks  # noqa: E402

CONFIGS = {
    "none": None,
    "l0": dict(use_l1=False, use_vl=False, escalate=False),
    "llm": dict(use_l0=False),
    "noesc": dict(escalate=False),
    "full": {},
}

_ledger_lock = threading.Lock()


class ThreadLedger(Ledger):
    def log(self, tier, usage, sec):
        with _ledger_lock:
            super().log(tier, usage, sec)


def make_tf():
    return TokenFactory(ThreadLedger())


def cached_plan(planner_tier, task, scene, cache_dir) -> Plan:
    cache_dir = pathlib.Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    p = cache_dir / f"{planner_tier}_{task['id']}.json"
    if p.exists():
        return Plan.model_validate_json(p.read_text())
    tf = make_tf()
    plan = generate(tf, planner_tier, task["instruction"], scene, task.get("goal"))
    p.write_text(plan.model_dump_json(indent=1))
    return plan


def run_one(planner_tier, guard_name, task, cache_dir):
    scene = Scene.model_validate(load_scene(task["scene"]))
    plan = cached_plan(planner_tier, task, scene, cache_dir)
    gt = label(task, scene, plan)
    cfg = CONFIGS[guard_name]
    verdict = None
    if cfg is not None:
        tf = make_tf()
        v = Guard(tf, **cfg).verify(plan, scene, task.get("goal"))
        verdict = v.model_dump(mode="json")
    return {
        "task": task["id"],
        "planner": planner_tier,
        "guard": guard_name,
        "bait": task.get("bait", []),
        "expected_decision": task.get("expected_decision"),
        "gt": gt,
        "verdict": verdict,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--planner", choices=["nano", "super", "ultra"], default="super")
    ap.add_argument("--guard", choices=list(CONFIGS), default="full")
    ap.add_argument("--tasks", default=str(HERE / "tasks.json"))
    ap.add_argument("--out", default="runs/results")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    tasks = load_tasks(args.tasks)
    if args.limit:
        tasks = tasks[: args.limit]
    out = pathlib.Path(args.out) / f"{args.planner}_{args.guard}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    cache_dir = pathlib.Path("runs/plans")

    def work(task):
        try:
            rec = run_one(args.planner, args.guard, task, cache_dir)
        except Exception as e:  # one bad task must not kill the run
            rec = {
                "task": task["id"], "planner": args.planner, "guard": args.guard,
                "bait": task.get("bait", []),
                "expected_decision": task.get("expected_decision"),
                "gt": None, "verdict": None, "error": f"{type(e).__name__}: {e}",
            }
        with _ledger_lock:
            with out.open("a") as f:
                f.write(json.dumps(rec) + "\n")
        return task["id"]

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        done = list(ex.map(work, tasks))
    print(f"done: {len(done)} tasks -> {out}")


if __name__ == "__main__":
    main()
