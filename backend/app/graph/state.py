"""Shared LangGraph state.

Every node reads from and writes to a single ``ResearchState`` object. Keeping
all workflow data in one typed structure is what makes the graph inspectable:
the API layer can serialize any snapshot of this state to show the user exactly
what the workflow knows at any point in time.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict
import operator


class Finding(TypedDict):
    """A single piece of evidence gathered during the research node."""

    query: str
    title: str
    snippet: str
    url: str


class ResearchState(TypedDict, total=False):
    """The single shared state object threaded through every node.

    ``total=False`` lets individual nodes populate only the keys they own while
    still giving us static-analysis-friendly typing for the whole workflow.
    """

    # --- Inputs (set once when the run starts) ---
    session_id: str
    company_name: str
    website: str
    objective: str

    # --- Planner node output ---
    plan: list[str]
    search_queries: list[str]

    # --- Research node output ---
    findings: list[Finding]
    sources: list[dict[str, str]]

    # --- Analysis node output ---
    analysis: dict[str, Any]

    # --- Quality-check node output ---
    quality_score: float
    quality_issues: list[str]
    quality_passed: bool

    # --- Report generation node output ---
    report: dict[str, Any]

    # --- Control / bookkeeping ---
    retries: int
    # ``operator.add`` makes these append-only across nodes instead of being
    # overwritten, so we accumulate a full audit trail of the run.
    logs: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]
