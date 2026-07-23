"""Web-search abstraction with graceful degradation.

Preference order:
    1. Tavily        — if ``TAVILY_API_KEY`` is set (best quality, needs a key).
    2. DuckDuckGo    — via the ``ddgs`` package, no key required.
    3. Offline stub  — deterministic synthetic results, clearly labelled.

Every provider returns the same shape: a list of ``{title, url, snippet}``.
The research node never has to know which one served the results, and a network
failure in any provider degrades to the stub instead of crashing the workflow.
"""

from __future__ import annotations

from typing import Any

from ..config import Settings, get_settings
from ..logging_config import get_logger

logger = get_logger("copilot.search")


def _tavily_search(query: str, k: int, settings: Settings) -> list[dict[str, str]]:
    import httpx

    resp = httpx.post(
        "https://api.tavily.com/search",
        json={
            "api_key": settings.tavily_api_key,
            "query": query,
            "max_results": k,
            "search_depth": "basic",
        },
        timeout=20.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", ""),
        }
        for r in data.get("results", [])
    ]


def _ddg_search(query: str, k: int) -> list[dict[str, str]]:
    # ``ddgs`` is the maintained successor to ``duckduckgo_search``.
    from ddgs import DDGS

    out: list[dict[str, str]] = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=k):
            out.append(
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", "") or r.get("url", ""),
                    "snippet": r.get("body", ""),
                }
            )
    return out


def _stub_search(query: str, k: int) -> list[dict[str, str]]:
    return [
        {
            "title": f"[stub] Result {i + 1} for '{query}'",
            "url": f"https://example.com/stub?q={query.replace(' ', '+')}&r={i + 1}",
            "snippet": (
                "Offline stub result. No live web search was performed. Configure "
                "TAVILY_API_KEY or install the 'ddgs' package with network access "
                "to retrieve real evidence."
            ),
        }
        for i in range(min(k, 2))
    ]


def search(query: str) -> dict[str, Any]:
    """Run one query and return ``{results, provider}``.

    Failures are swallowed and downgraded to the stub so a single flaky query
    can never take down an entire research run.
    """
    settings = get_settings()
    k = settings.search_results_per_query

    if settings.search_mode == "tavily":
        try:
            return {"results": _tavily_search(query, k, settings), "provider": "tavily"}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Tavily search failed for %r (%s); trying DuckDuckGo", query, exc)

    try:
        results = _ddg_search(query, k)
        if results:
            return {"results": results, "provider": "duckduckgo"}
        logger.info("DuckDuckGo returned no results for %r; using stub", query)
    except Exception as exc:  # noqa: BLE001
        logger.warning("DuckDuckGo search failed for %r (%s); using stub", query, exc)

    return {"results": _stub_search(query, k), "provider": "stub"}
