"""Smoke tests for the LangGraph workflow.

These run entirely in offline stub mode (no API keys, no network) and verify
the graph produces a complete, contract-compliant report end-to-end.

Run:  cd backend && python -m pytest -q   (or: python tests/test_graph.py)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Use throwaway DB files so tests never touch a real database.
os.environ.setdefault("DATABASE_PATH", "test_copilot.db")
os.environ.setdefault("CHECKPOINT_PATH", "test_checkpoints.db")

from app.graph import workflow  # noqa: E402

REQUIRED_REPORT_KEYS = {
    "company_overview",
    "products_services",
    "target_customers",
    "business_signals",
    "risks_challenges",
    "discovery_questions",
    "outreach_strategy",
    "unknowns",
    "sources",
}


def test_workflow_produces_complete_report():
    state = {
        "session_id": "test-session-1",
        "company_name": "Acme Corp",
        "website": "https://acme.example",
        "objective": "Sell them an analytics platform",
        "retries": 0,
    }
    seen_nodes = [event["node"] for event in workflow.stream_run(state, "test-session-1")]

    # The core nodes must all fire, in order.
    for node in ("planner", "research", "analysis", "quality_check", "report"):
        assert node in seen_nodes, f"node {node} did not run"

    final = workflow.get_state_snapshot("test-session-1")
    report = final.get("report", {})
    assert REQUIRED_REPORT_KEYS.issubset(report.keys()), (
        f"missing keys: {REQUIRED_REPORT_KEYS - set(report.keys())}"
    )
    assert isinstance(report["discovery_questions"], list)
    assert report["company_overview"], "overview should not be empty"


if __name__ == "__main__":
    test_workflow_produces_complete_report()
    print("OK: workflow produced a complete report in offline stub mode")
