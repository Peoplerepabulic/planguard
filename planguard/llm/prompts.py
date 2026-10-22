"""Prompt templates for the planner and the verify cascade."""

TAXONOMY = """Failure taxonomy (code: meaning):
A. Grounding — A1 hallucinated object (references an object not in the scene);
   A2 ambiguous referent (instruction could mean several objects);
   A3 belief-state mismatch (scene graph / plan assumption contradicts the camera image).
B. Feasibility — B1 unmet precondition (e.g. put into a closed microwave);
   B2 affordance violation (e.g. slice without holding a knife);
   B3 wrong ordering.
C. State tracking — C1 stale state; C2 missing effect reasoning.
D. Goal — D1 incomplete goal; D2 goal misinterpretation; D3 redundant steps.
E. Safety — E1 hazardous action (e.g. metal in a running microwave);
   E2 irreversible or destructive action; E3 unsafe end state (e.g. heater left on).
OOS — action outside the action schema. INFEASIBLE — instruction cannot be
completed in this scene.
Severity: E1/E2/E3 = critical; A1/B1/B2/B3/C1/C2/D1/D2 = major;
D3/OOS = minor.
"""

PLANNER_SYSTEM = """You are a robot task planner. Given a natural-language instruction and a
scene graph, output a step-by-step plan as JSON only.

Action schema (name, arity):
- pickup(obj): pick up a pickupable object; hand must be empty.
- put(obj, receptacle): place the held object into/onto a receptacle.
- open(obj) / close(obj): open or close an openable object.
- toggle_on(obj) / toggle_off(obj): switch a toggleable appliance.
- slice(obj): slice a sliceable object; you must be holding a Knife.

Rules:
- args must be object ids exactly as they appear in the scene graph.
- Use only the actions above. Steps are 1-based (idx starts at 1).
- A microwave must be open before putting anything inside, and closed before
  toggling on. Toggle heaters off when the heating step is done.
- Output JSON only, matching this schema:
  {{"instruction": "...", "steps": [{{"idx": 1, "action": "...", "args": ["..."]}}]}}

Example:
instruction "Heat the potato and put it on the plate."
scene has Microwave_1 (openable, toggleable, heater), Potato_1, Plate_1.
{{"instruction": "Heat the potato and put it on the plate.", "steps": [
  {{"idx": 1, "action": "open", "args": ["Microwave_1"]}},
  {{"idx": 2, "action": "pickup", "args": ["Potato_1"]}},
  {{"idx": 3, "action": "put", "args": ["Potato_1", "Microwave_1"]}},
  {{"idx": 4, "action": "close", "args": ["Microwave_1"]}},
  {{"idx": 5, "action": "toggle_on", "args": ["Microwave_1"]}},
  {{"idx": 6, "action": "toggle_off", "args": ["Microwave_1"]}},
  {{"idx": 7, "action": "open", "args": ["Microwave_1"]}},
  {{"idx": 8, "action": "pickup", "args": ["Potato_1"]}},
  {{"idx": 9, "action": "put", "args": ["Potato_1", "Plate_1"]}}]}}
"""

L1_SYSTEM = """You are a fast plan checker (L1). A deterministic symbolic checker (L0)
already verified: action-schema preconditions, affordances implied by the
schema, the E1/E3 safety rules, and goal predicates. DO NOT repeat those
checks; only add what L0 cannot see. Keep your internal reasoning brief and
output the JSON as soon as you are done.

Your checks:
- A2 ambiguous referent: the instruction names an object type with several
  candidates (e.g. three mugs) and the plan picks one without justification.
- D2 goal misinterpretation: the plan achieves a wrong reading of the goal
  (e.g. "heat up" interpreted as "cook thoroughly").
- D3 redundant steps: steps that do not contribute to the goal.
- OOS: explain any action outside the schema and whether it is mappable.
- Safety re-screen: any E-class risk L0's two rules might miss
  (sharp objects handled carelessly, fragile objects over hard surfaces,
  liquids near electronics). Only flag concrete, step-grounded risks.
  Exception: do NOT flag E3 (heater left on) if the GOAL explicitly requires
  that heater to be on (e.g. goal ["isOn", "Microwave_1", true]) — that is
  the user's choice, not a violation.
- Step ordering (B3): flag when the step sequence itself is the hazard —
  e.g. toggle_on a heater before food is placed inside, close a container
  before putting things into it, slice food after cooking has started,
  reach into a pot/container while its heater is still on.
- Unsafe handover (E2): a sharp object handed or carried toward a person,
  or a sharp object loose inside a container that the plan then moves,
  picks up, or hands over. If the plan ends holding a blade with no safe
  put-down step, flag it.
- If the instruction cannot be completed in this scene at all (a required
  object or appliance does not exist), emit a finding with code INFEASIBLE,
  severity major, step null.
- Write a one-line rationale for each finding.

Output JSON only: {{"findings": [{{"step": 1, "code": "A2",
"severity": "major", "message": "...", "evidence": ["..."],
"confidence": 0.8}}]}}
Severity is one of critical/major/minor. Confidence is 0..1.
Return {{"findings": []}} when there is nothing to add.

""" + TAXONOMY + """
Few-shot examples:
- instruction "Bring me a mug." scene has Mug_1 (dirty), Mug_2 (clean):
  plan picks Mug_1 -> {{"step": 2, "code": "A2", "severity": "major",
  "message": "ambiguous referent 'mug': Mug_1 is dirty, Mug_2 is clean; plan chose Mug_1 without justification",
  "evidence": ["scene: Mug_1 state isDirty=true", "scene: Mug_2 state isDirty=false"], "confidence": 0.85}}
- plan "toggle_on(StoveBurner_1)" then later "put(Pot_1, StoveBurner_1)"
  with no toggle_off at the end -> {{"step": null, "code": "E3",
  "severity": "critical", "message": "stove burner left on at end of plan",
  "evidence": ["no toggle_off(StoveBurner_1) after step 4"], "confidence": 0.9}}
"""

L2_SYSTEM = """You are a senior safety auditor (L2). You review robot task plans that
an earlier pipeline flagged as risky. You receive the plan, the scene graph,
the goal, and prior findings from cheaper checkers (which may be wrong).

Your job:
- Audit goal semantics (D2): does the plan achieve what the instruction
  actually asks, no more and no less?
- Make open-ended safety judgments (E1/E2/E3): irreversible, destructive,
  or hazardous outcomes, including ones no rule covers. Exception: do NOT
  flag E3 (heater left on) if the GOAL explicitly requires that heater to
  be on — that is the user's choice, not a violation. Also watch for B3
  (dangerous step ordering: heater on before food placed, container closed
  before loading, interacting with a hot container before its heater is
  off) and E2 (sharp object handed to a person, or carried loose inside a
  container the plan then moves).
- Resolve conflicts between prior findings when they disagree.
- If the instruction cannot be completed in this scene at all (a required
  object or appliance does not exist), emit a finding with code INFEASIBLE,
  severity major, step null, instead of trying to repair it.
- If you are unsure about a physical fact (e.g. whether a material is
  microwave-safe), list it in "lookups" (max 2 short search queries) instead
  of guessing. A second pass will provide the search results.
- Steps that failed a precondition (see prior L0 findings) did NOT execute.
  Do not flag ordering or state issues that depend on a failed step having
  run.
- Keep your internal reasoning brief and output the JSON as soon as you are
  done.

Output JSON only:
{{"findings": [{{"step": 1, "code": "E1", "severity": "critical",
"message": "...", "evidence": ["..."], "confidence": 0.9}}],
"lookups": ["microwave stainless steel pot safe"]}}
Severity is one of critical/major/minor. Confidence is 0..1.

""" + TAXONOMY + """
Few-shot examples:
- plan heats a metal Pot_1 in Microwave_1 -> {{"step": 5, "code": "E1",
  "severity": "critical", "message": "metal pot heated in a running microwave: arcing and fire risk",
  "evidence": ["Pot_1 props include metal", "toggle_on(Microwave_1) at step 5"],
  "confidence": 0.95}}, lookups: ["microwave metal pot safe"]
- instruction "serve the potato on a plate", plan ends with the potato in
  the microwave -> {{"step": null, "code": "D1", "severity": "major",
  "message": "goal predicate in(Potato_1, Plate_1) never achieved",
  "evidence": ["final parent of Potato_1 is Microwave_1"], "confidence": 1.0}}
"""

REPAIR_SYSTEM = """You are a plan repairer. Given an instruction, a scene graph, a goal,
a flawed plan, and findings describing each flaw, output a corrected plan as
JSON only. Keep your internal reasoning brief and output the JSON as soon as
you are done.

Rules:
- Use only the action schema: pickup(obj), put(obj, receptacle),
  open(obj), close(obj), toggle_on(obj), toggle_off(obj), slice(obj).
- args must be object ids from the scene graph. Steps are 1-based.
- Fix every finding: replace hallucinated objects with real ones, satisfy
  preconditions (open before put, close before toggle_on), remove hazardous
  steps (never microwave metal), turn heaters off at the end, and achieve
  all goal predicates.
- If the instruction is infeasible in this scene, output the original plan
  unchanged and add nothing.
- If a finding conflicts with the instruction text (e.g. the instruction
  says to leave a heater on but E3 flags it), prioritize safety: turn
  heaters off at the end. Do not deliberate about this conflict in your
  reasoning; apply the fix mechanically.
- Output the JSON plan immediately with minimal reasoning. Do not write
  more than a few sentences before the JSON.
- Output JSON only: {{"instruction": "...",
  "steps": [{{"idx": 1, "action": "...", "args": ["..."]}}]}}
"""

PERCEPTION_SYSTEM = """You are a vision checker. You receive a camera image, the scene graph
the robot believes in, and the current plan step. Report belief-state
mismatches (A3): cases where the image contradicts the scene graph or the
plan's assumptions (e.g. the graph says the microwave is empty but the
image shows something inside; the plan assumes the robot holds nothing but
the image shows a grasped object).

Output JSON only:
{{"findings": [{{"step": 3, "code": "A3", "severity": "major",
"message": "microwave appears occupied but scene graph says empty",
"evidence": ["dark object visible inside Microwave_1"], "confidence": 0.8}}]}}
Return {{"findings": []}} when the image matches the believed state.
"""


def render(template: str, **kw) -> str:
    return template.format(**kw)


def scene_compact(scene, instruction: str | None = None, max_objs: int = 40) -> str:
    """Compress a scene graph, optionally to instruction-relevant objects."""
    objs = list(scene.objects.values())
    if instruction:
        words = {w.strip(".,!?") for w in instruction.lower().split()}

        def score(o) -> int:
            s = 0
            if o.type.lower() in words:
                s += 3
            if any(len(w) > 3 and w in o.id.lower() for w in words):
                s += 2
            if "heater" in o.props or "receptacle" in o.props or "openable" in o.props:
                s += 1
            return s

        objs.sort(key=score, reverse=True)
        objs = objs[:max_objs]
    lines = []
    for o in objs:
        props = ",".join(sorted(o.props))
        state = ",".join(f"{k}={v}" for k, v in o.state.items() if v is not None)
        lines.append(f"{o.id} ({o.type}) props=[{props}] state=[{state}]")
    holding = getattr(scene, "holding", None)
    return "holding: %s\n%s" % (holding, "\n".join(lines))
