"""Assemble and compile the LangGraph workflow.

Graph shape::

    START
      │
      ▼
    planner ──► research ──► analysis ──► quality_check
                   ▲                          │
                   │                          │ (conditional)
                 refine ◄──── retry ──────────┤
                                              │ report
                                              ▼
                                            report ──► END

The conditional edge out of ``quality_check`` is what makes this a real graph
rather than a linear pipeline: a low-quality analysis loops back through
``refine`` → ``research`` (up to ``MAX_RESEARCH_RETRIES``) before giving up and
generating the best report it can.

Recoverability comes from a SQLite checkpointer. Every run is keyed by a
``thread_id`` (== the session id), so LangGraph persists the state after each
node and a crashed/interrupted run can be resumed from its last checkpoint.
"""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from typing import Iterator

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from ..config import get_settings
from ..logging_config import get_logger
from . import nodes
from .state import ResearchState

logger = get_logger("copilot.workflow")


def _build_graph() -> StateGraph:
    graph = StateGraph(ResearchState)

    graph.add_node("planner", nodes.planner_node)
    graph.add_node("research", nodes.research_node)
    graph.add_node("analysis", nodes.analysis_node)
    graph.add_node("quality_check", nodes.quality_check_node)
    graph.add_node("refine", nodes.refine_node)
    graph.add_node("report", nodes.report_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "research")
    graph.add_edge("research", "analysis")
    graph.add_edge("analysis", "quality_check")

    # Conditional routing based on the quality score.
    graph.add_conditional_edges(
        "quality_check",
        nodes.route_after_quality,
        {"retry": "refine", "report": "report"},
    )
    graph.add_edge("refine", "research")  # the recoverability / refinement loop
    graph.add_edge("report", END)

    return graph


@lru_cache
def get_compiled_graph():
    """Compile once and reuse. Uses a persistent SQLite checkpointer."""
    settings = get_settings()
    conn = sqlite3.connect(settings.checkpoint_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    compiled = _build_graph().compile(checkpointer=checkpointer)
    logger.info("LangGraph workflow compiled with SQLite checkpointer")
    return compiled


# Human-friendly labels + ordering for the progress UI.
NODE_LABELS = {
    "planner": "Planning research",
    "research": "Gathering evidence",
    "analysis": "Analyzing findings",
    "quality_check": "Quality check",
    "refine": "Refining queries",
    "report": "Writing briefing",
}
NODE_ORDER = ["planner", "research", "analysis", "quality_check", "refine", "report"]


def stream_run(state: ResearchState, thread_id: str) -> Iterator[dict]:
    """Yield one event per completed node.

    Each event is ``{node, label, update}`` where ``update`` is the partial
    state that node produced — exactly what the UI needs to show progress.
    """
    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": thread_id}}
    for step in graph.stream(state, config=config, stream_mode="updates"):
        for node_name, update in step.items():
            yield {
                "node": node_name,
                "label": NODE_LABELS.get(node_name, node_name),
                "update": update,
            }


def get_state_snapshot(thread_id: str) -> dict:
    """Return the latest checkpointed state for a thread (for recoverability)."""
    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph.get_state(config)
    return dict(snapshot.values) if snapshot and snapshot.values else {}
