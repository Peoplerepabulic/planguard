"""L2: Nemotron Ultra auditor with two-stage Tavily grounding."""

from pydantic import BaseModel, Field

from ..grounding import tavily
from ..llm.prompts import L2_SYSTEM, render, scene_compact
from ..schema import Finding


class AuditOut(BaseModel):
    findings: list[Finding]
    lookups: list[str] = Field(default_factory=list)


def audit(tf, plan, scene, goal, prior) -> list[Finding]:
    import time as _time

    user = (
        f"Instruction: {plan.instruction}\nGoal: {goal}\nScene:\n{scene_compact(scene)}\n\n"
        f"Plan:\n{plan.model_dump_json(indent=1)}\n\n"
        f"Prior findings:\n{[f.model_dump(mode='json') for f in prior] or 'none'}\n\n"
        "Return JSON only."
    )
    out = tf.json("ultra", L2_SYSTEM, user, AuditOut, max_tokens=6000)
    if out.lookups:
        t0 = _time.perf_counter()
        ev = [tavily.search(q) for q in out.lookups[:2]]
        tf.ledger.lat["tavily"] += (_time.perf_counter() - t0) * 1000
        ev = [e for e in ev if e]  # drop failed lookups
        if ev:
            user2 = user + f"\n\nWeb evidence (with sources):\n{ev}\n\nRe-audit with this evidence. Return JSON only."
            out = tf.json("ultra", L2_SYSTEM, user2, AuditOut, max_tokens=6000)
    for f in out.findings:
        f.layer = "L2"
    return out.findings
