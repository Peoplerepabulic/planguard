"""Goal predicate checker."""

from ..schema import Scene
from .physics import contained_in


def unmet(s: Scene, goal: list[list]) -> list[list]:
    out = []
    for g in goal:
        if g[0] == "in":
            ok = g[1] in s.objects and contained_in(s, g[1], g[2])
        elif g[0] == "holding":
            ok = s.holding == g[1] if len(g) < 3 else (s.holding == g[1]) == g[2]
        else:
            ok = g[1] in s.objects and s.objects[g[1]].state.get(g[0]) == g[2]
        if not ok:
            out.append(g)
    return out
