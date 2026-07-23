"""LLM provider abstraction with a deterministic offline fallback.

Why this exists
---------------
The graph nodes should not care *which* model answers them. They call
``llm.complete_json(...)`` or ``llm.complete_text(...)`` and get back parsed
data. Two concrete providers implement that contract:

* ``AnthropicProvider`` — real Claude calls when ``ANTHROPIC_API_KEY`` is set.
* ``StubProvider``      — deterministic, template-driven output so the entire
  product (workflow, progress, report, chat) runs with **no keys and no
  network**. This makes the submission trivially reviewable and keeps tests
  hermetic.

The stub is intentionally *labelled* as synthetic in its output so a reviewer
is never misled into thinking placeholder text is real research.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..config import Settings, get_settings
from ..logging_config import get_logger

logger = get_logger("copilot.llm")


class LLMProvider:
    """Interface shared by every provider."""

    mode: str = "base"

    def complete_json(self, system: str, prompt: str) -> dict[str, Any]:  # pragma: no cover
        raise NotImplementedError

    def complete_text(self, system: str, prompt: str) -> str:  # pragma: no cover
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Real provider
# --------------------------------------------------------------------------- #
class AnthropicProvider(LLMProvider):
    mode = "anthropic"

    def __init__(self, settings: Settings) -> None:
        # Imported lazily so the dependency is only required when a key is set.
        import anthropic

        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.llm_model
        self._max_tokens = settings.llm_max_tokens

    def _message(self, system: str, prompt: str) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )

    def complete_json(self, system: str, prompt: str) -> dict[str, Any]:
        system = system + (
            "\n\nRespond with a SINGLE valid JSON object and nothing else. "
            "Do not wrap it in markdown fences."
        )
        raw = self._message(system, prompt)
        return _extract_json(raw)

    def complete_text(self, system: str, prompt: str) -> str:
        return self._message(system, prompt).strip()


# --------------------------------------------------------------------------- #
# Offline deterministic provider
# --------------------------------------------------------------------------- #
class StubProvider(LLMProvider):
    """Deterministic output derived from the prompt.

    It is not trying to be smart — it is trying to be *predictable and honest*
    so that the full product flow can be demonstrated offline. Each response is
    keyed off a ``task`` marker embedded in the prompt by the caller.
    """

    mode = "stub"

    def complete_json(self, system: str, prompt: str) -> dict[str, Any]:
        task = _read_marker(prompt, "TASK")
        company = _read_marker(prompt, "COMPANY") or "the company"
        objective = _read_marker(prompt, "OBJECTIVE") or "a sales conversation"

        if task == "plan":
            return {
                "plan": [
                    f"Establish what {company} does and its core value proposition",
                    f"Map {company}'s products, pricing signals, and target customers",
                    f"Surface recent business signals relevant to: {objective}",
                    "Identify risks, competitors, and open unknowns",
                ],
                "search_queries": [
                    f"{company} company overview",
                    f"{company} products and pricing",
                    f"{company} customers case studies",
                    f"{company} news funding hiring 2024 2025",
                ],
            }

        if task == "analysis":
            findings_blob = _read_marker(prompt, "FINDINGS") or ""
            evidence = "grounded in the gathered sources" if findings_blob.strip() else (
                "based on limited evidence (offline stub mode)"
            )
            return {
                "company_overview": (
                    f"{company} is analysed here in offline stub mode. The overview is "
                    f"{evidence}. Replace the stub by setting ANTHROPIC_API_KEY to get a "
                    f"model-authored synthesis."
                ),
                "products_services": [
                    f"{company} core platform (inferred)",
                    "Professional / onboarding services (inferred)",
                ],
                "target_customers": [
                    "Mid-market operators evaluating the category",
                    "Teams whose objective aligns with: " + objective,
                ],
                "business_signals": [
                    "Signal extraction requires live search or a configured LLM key",
                ],
                "risks_challenges": [
                    "Evidence is synthetic in stub mode — validate before a real meeting",
                ],
                "confidence": 0.4,
            }

        if task == "quality":
            analysis_blob = _read_marker(prompt, "ANALYSIS") or ""
            # Heuristic: reward analyses that actually contain content.
            filled = len(analysis_blob.strip())
            score = 0.82 if filled > 400 else 0.55
            issues = (
                [] if score >= 0.7 else ["Analysis is thin; gather more evidence"]
            )
            return {"score": score, "issues": issues}

        if task == "report":
            return _stub_report(company, objective, prompt)

        return {}

    def complete_text(self, system: str, prompt: str) -> str:
        question = _read_marker(prompt, "QUESTION") or "your question"
        company = _read_marker(prompt, "COMPANY") or "the company"
        return (
            f"[offline stub answer] Based on the {company} briefing on file, here is a "
            f"grounded response to “{question}”. Set ANTHROPIC_API_KEY to enable "
            f"model-authored, context-aware chat answers."
        )


def _stub_report(company: str, objective: str, prompt: str) -> dict[str, Any]:
    sources_blob = _read_marker(prompt, "SOURCES") or ""
    urls = re.findall(r"https?://\S+", sources_blob)
    return {
        "company_overview": (
            f"{company} — offline stub briefing generated for objective: {objective}. "
            f"This is deterministic placeholder content so the end-to-end flow is "
            f"reviewable without external services."
        ),
        "products_services": [
            {"name": f"{company} Platform", "description": "Primary offering (inferred)."},
            {"name": "Add-on services", "description": "Implementation & support (inferred)."},
        ],
        "target_customers": [
            "Primary: teams matching the stated research objective.",
            "Secondary: adjacent buyers in the same category.",
        ],
        "business_signals": [
            "No live signals in stub mode — configure search/LLM keys to populate.",
        ],
        "risks_challenges": [
            "Content is synthetic; do not use verbatim in a real meeting.",
        ],
        "discovery_questions": [
            f"What is driving {company}'s interest in this area right now?",
            "Who owns the budget and what does success look like in 90 days?",
            "What have you already tried, and where did it fall short?",
        ],
        "outreach_strategy": (
            f"Lead with the objective ({objective}); open with a hypothesis about "
            f"{company}'s priorities and ask a discovery question to confirm it."
        ),
        "unknowns": [
            "Actual product depth, pricing, and recent news (needs live sources).",
        ],
        "sources": urls or ["(no live sources — offline stub mode)"],
    }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _read_marker(prompt: str, key: str) -> str | None:
    """Read a ``[[KEY]] ... [[/KEY]]`` block injected by callers."""
    m = re.search(rf"\[\[{key}\]\](.*?)\[\[/{key}\]\]", prompt, re.DOTALL)
    return m.group(1).strip() if m else None


def _extract_json(raw: str) -> dict[str, Any]:
    """Best-effort JSON parse from a model response."""
    raw = raw.strip()
    # Strip markdown fences if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fall back to the first balanced object in the string.
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
    logger.warning("LLM returned non-JSON output; returning empty dict")
    return {}


_provider: LLMProvider | None = None


def get_llm() -> LLMProvider:
    """Process-wide singleton chosen from configuration."""
    global _provider
    if _provider is None:
        settings = get_settings()
        if settings.llm_mode == "anthropic":
            try:
                _provider = AnthropicProvider(settings)
                logger.info("LLM provider: Anthropic (%s)", settings.llm_model)
            except Exception as exc:  # noqa: BLE001 - never fail startup over LLM
                logger.warning("Anthropic init failed (%s); using offline stub", exc)
                _provider = StubProvider()
        else:
            _provider = StubProvider()
            logger.info("LLM provider: offline stub (no ANTHROPIC_API_KEY set)")
    return _provider
