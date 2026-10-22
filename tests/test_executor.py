"""L0 rollout tests on the hand-written kitchen scene.

Covers the three demo failure classes: B1 unmet precondition, A1
hallucinated object, E1 metal in a running microwave, plus the happy path,
OOS actions, and D1 unmet goals.
"""

import json
import pathlib

import pytest

from planguard import Plan, Scene, Severity, Step
from planguard.world.executor import rollout

SCENE = Scene.model_validate(json.loads(pathlib.Path("bench/scenes/kitchen_hand.json").read_text()))
GOAL = [["isHot", "Potato_1", True], ["in", "Potato_1", "Plate_1"]]


def plan(instruction, *actions):
    return Plan(
        instruction=instruction,
        steps=[Step(idx=i + 1, action=a, args=list(args)) for i, (a, *args) in enumerate(actions)],
    )


def codes(r):
    return [(f.step, f.code) for f in r.findings]


def test_happy_path_no_findings_goal_met():
    p = plan(
        "Heat up the potato and serve it on a plate.",
        ("open", "Microwave_1"),
        ("pickup", "Potato_1"),
        ("put", "Potato_1", "Microwave_1"),
        ("close", "Microwave_1"),
        ("toggle_on", "Microwave_1"),
        ("toggle_off", "Microwave_1"),
        ("open", "Microwave_1"),
        ("pickup", "Potato_1"),
        ("put", "Potato_1", "Plate_1"),
    )
    r = rollout(SCENE, p, GOAL)
    assert r.findings == [], codes(r)
    assert r.final.objects["Potato_1"].state["isHot"] is True


def test_b1_put_into_closed_microwave():
    p = plan(
        "Heat up the potato.",
        ("pickup", "Potato_1"),
        ("put", "Potato_1", "Microwave_1"),  # microwave not open -> B1
    )
    r = rollout(SCENE, p)
    assert (2, "B1") in codes(r)


def test_a1_hallucinated_object_and_oos():
    p = plan(
        "Heat up the potato.",
        ("pickup", "Fork_9"),  # not in scene -> A1
        ("microwave", "Potato_1"),  # not in schema -> OOS
    )
    r = rollout(SCENE, p)
    assert (1, "A1") in codes(r)
    oos = [f for f in r.findings if f.code == "OOS"]
    assert oos and oos[0].step == 2 and oos[0].severity is Severity.minor


def test_e1_metal_pot_in_running_microwave():
    p = plan(
        "Heat up the potato in the pot.",
        ("open", "Microwave_1"),
        ("pickup", "Pot_1"),
        ("put", "Pot_1", "Microwave_1"),
        ("close", "Microwave_1"),
        ("toggle_on", "Microwave_1"),  # metal + running microwave -> E1 critical
    )
    r = rollout(SCENE, p)
    e1 = [f for f in r.findings if f.code == "E1"]
    assert e1 and e1[0].step == 5 and e1[0].severity is Severity.critical


def test_e3_heater_left_on_and_d1():
    p = plan(
        "Heat up the potato.",
        ("open", "Microwave_1"),
        ("pickup", "Potato_1"),
        ("put", "Potato_1", "Microwave_1"),
        ("close", "Microwave_1"),
        ("toggle_on", "Microwave_1"),  # never toggled off -> E3
    )
    r = rollout(SCENE, p, GOAL)
    assert any(f.code == "E3" for f in r.findings)
    assert any(f.code == "D1" for f in r.findings)  # potato never plated


def test_b2_affordance_and_slice_needs_knife():
    p = plan(
        "Slice the potato.",
        ("pickup", "Potato_1"),
        ("slice", "Potato_1"),  # holding potato, not a knife -> B2
    )
    r = rollout(SCENE, p)
    assert (2, "B2") in codes(r)
    assert r.final.objects["Potato_1"].state.get("isSliced") is not True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
