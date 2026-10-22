"""Cost and latency ledger with a daily budget guard."""

import json
import pathlib
import time
from collections import defaultdict

# USD per 1M tokens: (input, output). Values marked EST are third-party
# estimates (Artificial Analysis / OpenRouter / cabina.ai, Oct 2026) until
# confirmed against the Token Factory console billing page.
PRICES: dict[str, tuple[float, float]] = {
    "nano": (0.08, 0.20),    # EST: Nemotron 3 Nano 30B A3B
    "lightning": (0.06, 0.16),  # EST: Nemotron 3.5 Lightning
    "super": (0.40, 1.60),   # EST: Nemotron 3 Super 120B — confirm in console
    "ultra": (0.50, 2.20),   # EST: Nemotron 3 Ultra 550B
    "vl": (0.30, 1.20),      # EST: Nemotron 3.5 Super VL — confirm in console
}


class BudgetExceeded(Exception):
    pass


class Ledger:
    def __init__(self, path="runs/ledger.jsonl", daily_cap: float | None = None):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.daily_cap = daily_cap
        self.reset()

    def reset(self):
        self.cost = 0.0
        self.lat = defaultdict(float)
        self.calls = defaultdict(int)

    def log(self, tier, usage, sec):
        pin, pout = PRICES.get(tier, (0.0, 0.0))
        c = (usage.prompt_tokens * pin + usage.completion_tokens * pout) / 1e6
        self.cost += c
        self.lat[tier] += sec * 1000
        self.calls[tier] += 1
        rec = dict(
            t=time.time(), tier=tier,
            pin=usage.prompt_tokens, pout=usage.completion_tokens,
            cost=c, sec=sec,
        )
        with self.path.open("a") as f:
            f.write(json.dumps(rec) + "\n")

    def spent_since(self, t0: float) -> float:
        if not self.path.exists():
            return 0.0
        rows = map(json.loads, self.path.read_text().splitlines())
        return sum(r["cost"] for r in rows if r["t"] >= t0)

    def check(self):
        if self.daily_cap is not None and self.spent_since(time.time() - 86400) >= self.daily_cap:
            raise BudgetExceeded

    def snapshot(self) -> dict:
        return {
            "cost_usd": round(self.cost, 6),
            "latency_ms": {k: round(v, 1) for k, v in self.lat.items()},
            "calls": dict(self.calls),
        }
