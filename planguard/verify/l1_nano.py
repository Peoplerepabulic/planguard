"""L1: Nemotron Nano step verifier. Covers what L0 cannot see."""

from pydantic import BaseModel

from ..llm.prompts import L1_SYSTEM, render, scene_compact
from ..schema import Finding


class L1Out(BaseModel):
    findings: list[Finding]


def check(tf, plan, scene, goal, prior_findings) -> list[Finding]:
    user = render(
        "{sys}\n\nInstruction: {instr}\nGoal: {goal}\nScene:\n{scene}\n\nPlan:\n{plan}\n\nL0 findings (do not repeat):\n{prior}\n\nReturn JSON only.",
        sys="(schema omitted in user turn)",
        instr=plan.instruction,
        goal=goal,
        scene=scene_compact(scene),
        plan=plan.model_dump_json(indent=1),
        prior=[f.model_dump(mode="json") for f in prior_findings] or "none",
    )
    out = tf.json("nano", L1_SYSTEM, user, L1Out, max_tokens=6000)
    for f in out.findings:
        f.layer = "L1"
    return out.findings
