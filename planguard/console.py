"""PlanGuard web console backend (FastAPI + rate limiting).

Serves the static frontend (built 10/26) and four API groups:
  POST /api/verify      live plan verification (10/day/IP + global daily cap)
  GET  /api/episodes    cached demo episodes (precomputed verdicts)
  GET  /api/benchmark   benchmark summary table
  GET  /api/cost        today's spend

Run: uvicorn planguard.console:app --host 0.0.0.0 --port 7860
Env: NEBIUS_API_KEY, TAVILY_API_KEY,
     PLANGUARD_DAILY_CAP_USD (default 2.0), PLANGUARD_DATA_DIR (default ./data)
"""

import json
import os
import pathlib

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .llm.ledger import BudgetExceeded
from .schema import Plan, Scene
from .verify import Guard

DATA = pathlib.Path(os.environ.get("PLANGUARD_DATA_DIR", "data"))
DAILY_CAP = float(os.environ.get("PLANGUARD_DAILY_CAP_USD", "2.0"))

app = FastAPI(title="PlanGuard Console")
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rl_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        {"error": "rate_limited", "detail": "10 verifications per day per IP."},
        status_code=429,
    )


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/verify")
@limiter.limit("10/day")
def verify(request: Request, body: dict):
    try:
        v = Guard.default(daily_cap=DAILY_CAP).verify(
            Plan.model_validate(body["plan"]),
            Scene.model_validate(body["scene"]),
            body.get("goal"),
        )
    except BudgetExceeded:
        return JSONResponse(
            {"error": "daily_cap", "detail": "Demo daily budget exhausted."},
            status_code=429,
        )
    return v.model_dump(mode="json")


def _read(name: str):
    p = DATA / name
    if not p.exists():
        return JSONResponse({"error": "not_ready"}, status_code=404)
    return json.loads(p.read_text())


@app.get("/api/episodes")
def episodes():
    return _read("episodes.json")


@app.get("/api/episodes/{eid}")
def episode(eid: str):
    eps = _read("episodes.json")
    if isinstance(eps, JSONResponse):
        return eps
    for e in eps:
        if e["id"] == eid:
            return e
    return JSONResponse({"error": "not_found"}, status_code=404)


@app.get("/api/benchmark")
def benchmark():
    return _read("benchmark.json")


@app.get("/api/cost")
def cost():
    return _read("cost.json")


# Static frontend (built separately into ./static); mounted last.
if pathlib.Path("static").exists():
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
