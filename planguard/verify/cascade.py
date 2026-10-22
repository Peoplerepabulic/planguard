"""Guard: orchestrates L0 -> L1 -> (VL) -> L2 cascade, then decides."""

from ..llm.client import TokenFactory
from ..llm.ledger import Ledger
from ..repair import repair
from ..schema import Plan, Scene, Severity, Verdict
from ..world.executor import rollout
from . import l1_nano, l2_ultra, perception

HIGH_RISK = {"toggle_on", "slice", "pour", "fill"}
ASK_HUMAN = {"A2", "INFEASIBLE"}


def needs_escalation(plan: Plan, l0_findings, l1_findings) -> bool:
    findings = l0_findings + l1_findings
    if any(
        f.severity is Severity.critical or f.confidence < 0.7 or f.code == "OOS"
        for f in findings
    ):
        return True
    if any(s.action in HIGH_RISK for s in plan.steps):
        return True
    # L0/L1 conflict heuristic: L0 found major+ issues but L1 added nothing.
    if any(f.severity is not Severity.minor for f in l0_findings) and not l1_findings:
        return True
    return False


def decide(findings) -> str:
    serious = [f for f in findings if f.severity is not Severity.minor]
    oos = [f for f in findings if f.code == "OOS"]
    if not serious and not oos:
        return "approve"
    if any(f.code in ASK_HUMAN for f in serious):
        return "ask_human"
    # OOS or other serious findings: Ultra regenerates the plan inside the
    # schema; if it cannot produce a clean plan, the caller maps to reject.
    return "repair"


class Guard:
    def __init__(self, tf: TokenFactory, use_l0=True, use_l1=True, use_vl=True, escalate=True):
        self.tf = tf
        self.use_l0 = use_l0
        self.use_l1 = use_l1
        self.use_vl = use_vl
        self.escalate = escalate

    @classmethod
    def default(cls, daily_cap: float | None = None, **kw) -> "Guard":
        ledger = Ledger(daily_cap=daily_cap)
        return cls(TokenFactory(ledger), **kw)

    def verify(
        self,
        plan: Plan,
        scene: Scene,
        goal=None,
        frame: bytes | None = None,
        max_repairs: int = 2,
    ) -> Verdict:
        self.tf.ledger.reset()
        l0 = rollout(scene, plan, goal).findings if self.use_l0 else []
        l1 = l1_nano.check(self.tf, plan, scene, goal, l0) if self.use_l1 else []
        findings = l0 + l1
        if self.use_vl and frame:
            findings += perception.check(self.tf, plan, scene, frame)
        escalated = self.escalate and needs_escalation(plan, l0, l1)
        if escalated:
            findings += l2_ultra.audit(self.tf, plan, scene, goal, findings)
        decision = decide(findings)
        repaired = None
        if decision == "repair":
            repaired = repair(self.tf, plan, scene, goal, findings, max_rounds=max_repairs)
            if repaired is None:
                decision = "reject"
        return Verdict(
            decision=decision,
            findings=findings,
            plan=plan,
            repaired=repaired,
            escalated=escalated,
            **self.tf.ledger.snapshot(),
        )
