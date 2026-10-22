"""Action schema: arity, precondition checks, and effects.

Check functions return a taxonomy code (e.g. "B1") when the precondition
fails, else None. They run in order; the first failure wins, so `exists`
must stay first to avoid KeyErrors on missing objects.
"""

from collections.abc import Callable

from ..schema import Scene

Check = Callable[[Scene, list[str]], str | None]
Effect = Callable[[Scene, list[str]], None]


def exists(s, a):
    return next(("A1" for o in a if o not in s.objects), None)


def hand_empty(s, a):
    return "B1" if s.holding else None


def holding(i=0):
    return lambda s, a: None if s.holding == a[i] else "B1"


def holding_type(t):
    return lambda s, a: None if s.holding and s.objects[s.holding].type == t else "B2"


def has(prop, i=0):
    return lambda s, a: None if prop in s.objects[a[i]].props else "B2"


def is_(key, val, i=0):
    return lambda s, a: None if bool(s.objects[a[i]].state.get(key)) == val else "B1"


def open_if_openable(i):
    def f(s, a):
        o = s.objects[a[i]]
        return "B1" if "openable" in o.props and not o.state.get("isOpen") else None

    return f


def set_(key, val, i=0):
    def f(s, a):
        s.objects[a[i]].state[key] = val

    return f


def do_pickup(s, a):
    s.holding = a[0]
    s.objects[a[0]].state["parent"] = None


def do_put(s, a):
    s.objects[a[0]].state["parent"] = a[1]
    s.holding = None


ACTIONS: dict[str, tuple[int, list[Check], list[Effect]]] = {
    "pickup": (1, [exists, hand_empty, has("pickupable")], [do_pickup]),
    "put": (2, [exists, holding(0), has("receptacle", 1), open_if_openable(1)], [do_put]),
    "open": (1, [exists, has("openable")], [set_("isOpen", True)]),
    "close": (1, [exists, has("openable"), is_("isOpen", True)], [set_("isOpen", False)]),
    "toggle_on": (1, [exists, has("toggleable")], [set_("isOn", True)]),
    "toggle_off": (1, [exists, has("toggleable"), is_("isOn", True)], [set_("isOn", False)]),
    "slice": (1, [exists, has("sliceable"), holding_type("Knife")], [set_("isSliced", True)]),
}
