"""Minimal physics: containment and heating ticks."""

from ..schema import Scene


def contained_in(s: Scene, oid: str, cid: str) -> bool:
    p = s.objects[oid].state.get("parent")
    while p:
        if p == cid:
            return True
        p = s.objects[p].state.get("parent") if p in s.objects else None
    return False


def tick(s: Scene) -> None:
    for h in s.objects.values():
        if "heater" in h.props and h.state.get("isOn"):
            for o in s.objects.values():
                if contained_in(s, o.id, h.id):
                    o.state["isHot"] = True
