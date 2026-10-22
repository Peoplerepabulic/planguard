"""L0 symbolic rollout: deterministic plan execution and checking."""

from dataclasses import dataclass, field

from ..schema import Finding, Plan, Scene, Severity
from .actions import ACTIONS
from .goals import unmet
from .physics import tick
from .safety import END_RULES, STEP_RULES

SEV = {
    "A1": Severity.major,
    "B1": Severity.major,
    "B2": Severity.major,
    "D1": Severity.major,
    "E1": Severity.critical,
    "E2": Severity.critical,
    "E3": Severity.critical,
}


@dataclass
class Rollout:
    final: Scene
    findings: list[Finding] = field(default_factory=list)
    trace: list[Scene] = field(default_factory=list)
    halted_at: int | None = None


def rollout(scene: Scene, plan: Plan, goal=None, halt_on_error=False) -> Rollout:
    s = scene.model_copy(deep=True)
    r = Rollout(final=s)
    for st in plan.steps:
        spec = ACTIONS.get(st.action)
        if spec is None or len(st.args) != spec[0]:
            r.findings.append(
                Finding(
                    step=st.idx,
                    code="OOS",
                    severity=Severity.minor,
                    message=f"{st.action}{st.args} not in schema",
                    confidence=0.5,
                )
            )
            continue
        _, checks, effects = spec
        err = next((c for c in (chk(s, st.args) for chk in checks) if c), None)
        if err:
            r.findings.append(
                Finding(
                    step=st.idx,
                    code=err,
                    severity=SEV[err],
                    message=f"{st.action}{st.args} failed {err}",
                )
            )
            if halt_on_error:
                r.halted_at = st.idx
                break
            continue
        for eff in effects:
            eff(s, st.args)
        tick(s)
        for code, rule in STEP_RULES:
            if msg := rule(s):
                r.findings.append(Finding(step=st.idx, code=code, severity=SEV[code], message=msg))
        r.trace.append(s.model_copy(deep=True))
    for code, rule in END_RULES:
        if msg := rule(s, goal):
            r.findings.append(Finding(code=code, severity=SEV[code], message=msg))
    if goal and (miss := unmet(s, goal)):
        r.findings.append(Finding(code="D1", severity=Severity.major, message=f"unmet goal: {miss}"))
    return r
