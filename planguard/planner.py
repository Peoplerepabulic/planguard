"""Planner: Nemotron Super generates a structured plan from instruction + scene."""

from .llm.prompts import PLANNER_SYSTEM, scene_compact
from .schema import Plan


def generate(tf, tier: str, instruction: str, scene, goal=None) -> Plan:
    user = (
        f"Instruction: {instruction}\n"
        f"Goal: {goal}\n"
        f"Scene:\n{scene_compact(scene, instruction)}\n\n"
        "Return JSON plan only."
    )
    return tf.json(tier, PLANNER_SYSTEM, user, Plan, max_tokens=6000)
