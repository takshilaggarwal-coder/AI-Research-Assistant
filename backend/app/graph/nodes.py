"""LangGraph node implementations.

Each node is a pure-ish function ``(state) -> partial_state``. It reads what it
needs from the shared :class:`ResearchState`, does one unit of work, and returns
only the keys it changed. LangGraph merges those updates back into the shared
state and passes it to the next node.

Design notes that map directly to the assignment's LangGraph requirements:

* **Multiple meaningful nodes** — planner / research / analysis / quality / report.
* **Shared graph state** — every node uses :class:`ResearchState`.
* **Intermediate outputs** — each node writes structured, inspectable output
  (``plan``, ``findings``, ``analysis``, ``quality_*``) that the API streams to
  the UI as it happens.
* **Failure handling** — every node is wrapped so an exception is recorded in
  ``state['errors']`` and the workflow continues with a safe fallback rather
  than crashing.
* **Recoverability** — combined with the SQLite checkpointer in ``workflow.py``,
  a run can resume from its last completed node.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from ..config import get_settings
from ..logging_config import get_logger
from ..services import search as search_service
from ..services.llm import get_llm
from .state import ResearchState

logger = get_logger("copilot.graph")


# --------------------------------------------------------------------------- #
# Node error-handling wrapper
# --------------------------------------------------------------------------- #
def _node(name: str) -> Callable:
    """Decorator: log entry/exit and convert exceptions into recorded errors."""

    def decorator(fn: Callable[[ResearchState], dict[str, Any]]):
        def wrapper(state: ResearchState) -> dict[str, Any]:
            logger.info("[%s] node start", name)
            try:
                update = fn(state)
                logger.info("[%s] node ok", name)
                update.setdefault("logs", [])
                update["logs"] = [f"{name}: completed"] + update.get("logs", [])
                return update
            except Exception as exc:  # noqa: BLE001 - resilience is the point
                logger.exception("[%s] node failed", name)
                return {
                    "errors": [f"{name}: {exc}"],
                    "logs": [f"{name}: FAILED ({exc}) — continuing with fallback"],
                }

        return wrapper

    return decorator


# --------------------------------------------------------------------------- #
# 1. Planner
# --------------------------------------------------------------------------- #
@_node("planner")
def planner_node(state: ResearchState) -> dict[str, Any]:
    """Turn the raw session inputs into a research plan + search queries."""
    llm = get_llm()
    prompt = (
        "You are planning a sales-research workflow.\n"
        "[[TASK]]plan[[/TASK]]\n"
        f"[[COMPANY]]{state['company_name']}[[/COMPANY]]\n"
        f"[[WEBSITE]]{state.get('website', '')}[[/WEBSITE]]\n"
        f"[[OBJECTIVE]]{state['objective']}[[/OBJECTIVE]]\n\n"
        "Produce a JSON object with:\n"
        '  "plan": a list of 3-5 concise research steps,\n'
        '  "search_queries": a list of 3-5 web search queries that will gather '
        "evidence for those steps."
    )
    data = llm.complete_json(
        system="You are a diligent B2B sales research planner.", prompt=prompt
    )
    plan = data.get("plan") or [f"Research {state['company_name']}"]
    queries = data.get("search_queries") or [f"{state['company_name']} overview"]
    return {"plan": plan, "search_queries": queries, "retries": state.get("retries", 0)}


# --------------------------------------------------------------------------- #
# 2. Research
# --------------------------------------------------------------------------- #
@_node("research")
def research_node(state: ResearchState) -> dict[str, Any]:
    """Execute each planned query and collect findings + de-duplicated sources."""
    queries = state.get("search_queries") or [f"{state['company_name']} overview"]
    findings: list[dict[str, str]] = []
    sources: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    providers: set[str] = set()

    for q in queries:
        result = search_service.search(q)
        providers.add(result["provider"])
        for r in result["results"]:
            findings.append(
                {
                    "query": q,
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", ""),
                    "url": r.get("url", ""),
                }
            )
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                sources.append({"title": r.get("title", ""), "url": url})

    logs = [f"research: {len(findings)} findings via {', '.join(sorted(providers))}"]
    return {"findings": findings, "sources": sources, "logs": logs}


# --------------------------------------------------------------------------- #
# 3. Analysis
# --------------------------------------------------------------------------- #
@_node("analysis")
def analysis_node(state: ResearchState) -> dict[str, Any]:
    """Synthesize raw findings into a structured intermediate analysis."""
    llm = get_llm()
    findings_text = "\n".join(
        f"- ({f['query']}) {f['title']}: {f['snippet']} [{f['url']}]"
        for f in state.get("findings", [])
    )
    prompt = (
        "Synthesize the research findings below into a structured analysis.\n"
        "[[TASK]]analysis[[/TASK]]\n"
        f"[[COMPANY]]{state['company_name']}[[/COMPANY]]\n"
        f"[[OBJECTIVE]]{state['objective']}[[/OBJECTIVE]]\n"
        f"[[FINDINGS]]{findings_text}[[/FINDINGS]]\n\n"
        "Return JSON with keys: company_overview (string), products_services (list), "
        "target_customers (list), business_signals (list), risks_challenges (list), "
        "confidence (0-1 float). Ground every claim in the findings; if evidence is "
        "missing, say so rather than inventing it."
    )
    analysis = llm.complete_json(
        system="You are a precise B2B research analyst who never fabricates facts.",
        prompt=prompt,
    )
    return {"analysis": analysis or {}}


# --------------------------------------------------------------------------- #
# 4. Quality check  (drives conditional routing)
# --------------------------------------------------------------------------- #
@_node("quality_check")
def quality_check_node(state: ResearchState) -> dict[str, Any]:
    """Score the analysis; the router uses this to decide retry vs. proceed."""
    settings = get_settings()
    llm = get_llm()
    analysis_text = json.dumps(state.get("analysis", {}), indent=2)
    prompt = (
        "Assess whether this analysis is complete enough to brief a salesperson.\n"
        "[[TASK]]quality[[/TASK]]\n"
        f"[[ANALYSIS]]{analysis_text}[[/ANALYSIS]]\n\n"
        'Return JSON: {"score": 0-1 float, "issues": [list of gaps]}.'
    )
    data = llm.complete_json(
        system="You are a strict quality reviewer.", prompt=prompt
    )
    score = float(data.get("score", 0.0) or 0.0)
    issues = data.get("issues", []) or []
    passed = score >= settings.quality_threshold
    logs = [
        f"quality_check: score={score:.2f} threshold={settings.quality_threshold} "
        f"passed={passed} retries={state.get('retries', 0)}"
    ]
    return {
        "quality_score": score,
        "quality_issues": issues,
        "quality_passed": passed,
        "logs": logs,
    }


def route_after_quality(state: ResearchState) -> str:
    """Conditional edge.

    * Below threshold **and** retry budget left -> loop back to ``research`` with
      an incremented retry counter (this is the recoverability/refinement loop).
    * Otherwise -> proceed to ``report``.
    """
    settings = get_settings()
    passed = state.get("quality_passed", False)
    retries = state.get("retries", 0)
    if not passed and retries < settings.max_research_retries:
        return "retry"
    return "report"


@_node("refine")
def refine_node(state: ResearchState) -> dict[str, Any]:
    """Widen the search queries before a retry and bump the retry counter."""
    base = state.get("search_queries", [])
    company = state["company_name"]
    widened = base + [
        f"{company} competitors alternatives",
        f"{company} reviews reputation",
    ]
    return {
        "search_queries": widened,
        "retries": state.get("retries", 0) + 1,
        "logs": ["refine: widened queries and incremented retry counter"],
    }


# --------------------------------------------------------------------------- #
# 5. Report generation
# --------------------------------------------------------------------------- #
@_node("report")
def report_node(state: ResearchState) -> dict[str, Any]:
    """Compose the final structured briefing with every required section."""
    llm = get_llm()
    analysis_text = json.dumps(state.get("analysis", {}), indent=2)
    sources_text = "\n".join(f"- {s['title']}: {s['url']}" for s in state.get("sources", []))
    prompt = (
        "Write the final sales-meeting briefing as JSON.\n"
        "[[TASK]]report[[/TASK]]\n"
        f"[[COMPANY]]{state['company_name']}[[/COMPANY]]\n"
        f"[[OBJECTIVE]]{state['objective']}[[/OBJECTIVE]]\n"
        f"[[ANALYSIS]]{analysis_text}[[/ANALYSIS]]\n"
        f"[[SOURCES]]{sources_text}[[/SOURCES]]\n\n"
        "Return JSON with EXACTLY these keys: company_overview (string), "
        "products_services (list), target_customers (list), business_signals (list), "
        "risks_challenges (list), discovery_questions (list), outreach_strategy "
        "(string), unknowns (list), sources (list of urls)."
    )
    report = llm.complete_json(
        system="You are an expert sales strategist writing a concise, honest briefing.",
        prompt=prompt,
    )
    # Guarantee the contract the frontend renders against, even if the model or
    # stub omitted a key.
    report.setdefault("company_overview", "")
    for key in (
        "products_services",
        "target_customers",
        "business_signals",
        "risks_challenges",
        "discovery_questions",
        "unknowns",
    ):
        report.setdefault(key, [])
    report.setdefault("outreach_strategy", "")
    report.setdefault("sources", [s["url"] for s in state.get("sources", [])])
    return {"report": report}
