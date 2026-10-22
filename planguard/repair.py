"""Repair loop: Ultra regenerates the plan, L0 re-verifies, up to N rounds."""

from .llm.prompts import REPAIR_SYSTEM, scene_compact
from .schema import Plan, Severity
from .world.executor import rollout


def repair(tf, plan: Plan, scene, goal, findings, max_rounds: int = 2) -> Plan | None:
    cur = plan
    for _ in range(max_rounds):
        user = (
            f"Instruction: {cur.instruction}\nGoal: {goal}\nScene:\n{scene_compact(scene)}\n\n"
            f"Flawed plan:\n{cur.model_dump_json(indent=1)}\n\n"
            f"Findings to fix:\n{[f.model_dump(mode='json') for f in findings]}\n\n"
            "Return corrected JSON plan only."
        )
        cand = tf.json("ultra", REPAIR_SYSTEM, user, Plan, max_tokens=6000)
        r = rollout(scene, cand, goal)
        serious = [f for f in r.findings if f.severity is not Severity.minor]
        oos = [f for f in r.findings if f.code == "OOS"]
        if not serious and not oos:
            return cand
        cur, findings = cand, r.findings
    return None
