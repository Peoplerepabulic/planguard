"""VL perception: Nemotron 3.5 Super VL checks image vs believed state (A3)."""

import base64
import time

from pydantic import BaseModel

from ..llm.prompts import PERCEPTION_SYSTEM, scene_compact
from ..schema import Finding


class PerceptionOut(BaseModel):
    findings: list[Finding]


def check(tf, plan, scene, frame: bytes, step: int | None = None) -> list[Finding]:
    b64 = base64.b64encode(frame).decode()
    body_user = [
        {
            "type": "text",
            "text": (
                f"Instruction: {plan.instruction}\nScene:\n{scene_compact(scene)}\n"
                f"Current step: {step}\nPlan:\n{plan.model_dump_json(indent=1)}\n\n"
                "Report belief-state mismatches (A3). Return JSON only."
            ),
        },
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    ]
    t = time.perf_counter()
    r = tf.c.chat.completions.create(
        model=tf.models["vl"],
        messages=[
            {"role": "system", "content": PERCEPTION_SYSTEM},
            {"role": "user", "content": body_user},
        ],
        response_format={"type": "json_object"},
        max_tokens=4000,
    )
    tf.ledger.log("vl", r.usage, time.perf_counter() - t)
    out = PerceptionOut.model_validate_json(r.choices[0].message.content or '{"findings": []}')
    for f in out.findings:
        f.layer = "VL"
    return out.findings
