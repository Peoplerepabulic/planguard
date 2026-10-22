"""Runtime Tavily search. Genuine live calls (needed for the bonus prize).

Degrades gracefully: on timeout/API error returns [] so the L2 auditor can
proceed with its first-pass findings instead of crashing the cascade.
"""

import logging
import os

from tavily import TavilyClient

log = logging.getLogger(__name__)

_client: TavilyClient | None = None


def _get() -> TavilyClient:
    global _client
    if _client is None:
        proxies = {}
        if os.environ.get("HTTPS_PROXY"):
            proxies["https"] = os.environ["HTTPS_PROXY"]
        if os.environ.get("HTTP_PROXY"):
            proxies["http"] = os.environ["HTTP_PROXY"]
        _client = TavilyClient(
            api_key=os.environ["TAVILY_API_KEY"],
            proxies=proxies or None,
        )
    return _client


def search(q: str, k: int = 3, timeout: int = 120) -> list[dict]:
    try:
        r = _get().search(q, max_results=k, timeout=timeout)
    except Exception as e:  # network/API failure -> degrade, don't crash
        log.warning("tavily search failed for %r: %s", q, e)
        return []
    return [
        {"title": x["title"], "url": x["url"], "snippet": x["content"][:500]}
        for x in r["results"]
    ]
