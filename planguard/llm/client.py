"""Token Factory client: OpenAI-compatible chat with JSON validation + retry."""

import os
import time

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from .ledger import Ledger

TIERS = ("nano", "super", "ultra", "vl", "lightning")

DEFAULT_MODELS = {
    "nano": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    "super": "nvidia/nemotron-3-super-120b-a12b",
    "ultra": "nvidia/Nemotron-3-Ultra-550b-a55b",
    "vl": "nvidia/Nemotron-3.5-Super-VL",
    "lightning": "nvidia/Nemotron-3_5-Lightning",
}


class TokenFactory:
    def __init__(
        self,
        ledger: Ledger,
        api_key: str | None = None,
        base_url: str | None = None,
        models: dict[str, str] | None = None,
    ):
        self.c = OpenAI(
            base_url=base_url or os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/"),
            api_key=api_key or os.environ["NEBIUS_API_KEY"],
            timeout=90.0,
            max_retries=1,
        )
        env_models = {t: os.environ.get(f"MODEL_{t.upper()}") for t in TIERS}
        self.models = {
            t: (models or {}).get(t) or env_models[t] or DEFAULT_MODELS[t] for t in TIERS
        }
        self.ledger = ledger

    def json(self, tier: str, system: str, user, out: type[BaseModel], retries: int = 1, **kw):
        """Chat completion parsed into a pydantic model, with one repair retry."""
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        for attempt in range(retries + 1):
            t = time.perf_counter()
            r = self.c.chat.completions.create(
                model=self.models[tier],
                messages=msgs,
                response_format={"type": "json_object"},
                **kw,
            )
            self.ledger.log(tier, r.usage, time.perf_counter() - t)
            txt = r.choices[0].message.content or ""
            try:
                return out.model_validate_json(txt)
            except ValidationError as e:
                msgs += [
                    {"role": "assistant", "content": txt},
                    {"role": "user", "content": f"Invalid for schema: {e}. Return corrected JSON only."},
                ]
        raise RuntimeError(f"{tier} failed schema {out.__name__} after {retries + 1} attempts")
