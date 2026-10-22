"""PlanGuard MCP server: expose verify_plan / repair_plan to any MCP client.

Run:  NEBIUS_API_KEY=... TAVILY_API_KEY=... python -m planguard.mcp_server
"""

from mcp.server.fastmcp import FastMCP

from .schema import Plan, Scene
from .verify import Guard

mcp = FastMCP("planguard")
_guard: Guard | None = None


def get_guard() -> Guard:
    global _guard
    if _guard is None:
        _guard = Guard.default()
    return _guard


@mcp.tool()
def verify_plan(plan: dict, scene: dict, goal: list | None = None) -> dict:
    """Run the full PlanGuard cascade on a plan.

    Returns a verdict: decision (approve/repair/ask_human/reject),
    findings with taxonomy codes and evidence, escalation flag, and
    cost/latency accounting.
    """
    v = get_guard().verify(
        Plan.model_validate(plan), Scene.model_validate(scene), goal
    )
    return v.model_dump(mode="json")


@mcp.tool()
def repair_plan(plan: dict, scene: dict, goal: list | None = None) -> dict:
    """Verify a plan and, if it needs repair, return the repaired plan.

    Returns {"verdict": ..., "repaired_plan": ...}; repaired_plan is null
    when the plan was already clean or could not be repaired.
    """
    p = Plan.model_validate(plan)
    s = Scene.model_validate(scene)
    v = get_guard().verify(p, s, goal)
    return {
        "verdict": v.model_dump(mode="json"),
        "repaired_plan": v.repaired.model_dump(mode="json") if v.repaired else None,
    }


if __name__ == "__main__":
    mcp.run()
