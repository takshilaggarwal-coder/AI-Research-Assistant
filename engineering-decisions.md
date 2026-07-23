# Engineering Decisions

Three decisions that shaped this build, the alternatives I weighed, and why I
chose what I did.

---

## Decision 1 — Provider abstraction with a deterministic offline fallback

**What I did.** Both the LLM and web-search layers sit behind small interfaces
(`llm.get_llm()`, `search.search()`). Each picks a concrete provider from config:
Anthropic Claude / Tavily if keys are present, DuckDuckGo (keyless) next, and a
deterministic **stub** as the final fallback. The whole product runs end-to-end
with no keys and no network.

**Alternatives considered.**
- *Require an API key.* Simplest to code; realistic output.
- *Mock only in tests.* Real providers in the app, fakes in the test suite.
- *Record/replay fixtures.* Capture real responses and replay them.

**Tradeoffs & why.** Requiring a key would have made the submission impossible to
evaluate without the reviewer spending money and doing setup — a bad first
impression for a product whose whole point is "just works." Mock-only-in-tests
wouldn't help a human clicking through the UI. The fallback stub costs me some
realism (its text is placeholder, clearly labelled), but it buys the single most
valuable property for a graded take-home: `pip install && npm run dev` and the
entire flow works. It also made the graph tests hermetic and fast. The
interface boundary means upgrading to real providers is a config change, not a
rewrite — so I didn't trade away production realism, only the *default*.

---

## Decision 2 — LangGraph with a quality-gated retry loop + SQLite checkpointer

**What I did.** Modeled the workflow as a `StateGraph` of six nodes with a
**conditional edge** out of `quality_check`: low score + retries remaining →
`refine → research` (loop), otherwise → `report`. State is checkpointed to SQLite
per run (`thread_id = session_id`).

**Alternatives considered.**
- *A linear LangChain chain / a plain Python function calling the LLM N times.*
- *A linear LangGraph with no branching* (satisfies "use LangGraph" minimally).
- *An agent with tool-calling* deciding its own steps.

**Tradeoffs & why.** A linear pipeline would have been less code, but the
assignment explicitly calls for conditional routing, recoverability, and failure
handling — and more importantly, a real research process *is* iterative: you
assess what you found and decide whether to dig further. The quality gate models
that honestly and demonstrates the branching requirement with a feature that
actually improves output. I rejected the free-form agent because
non-deterministic control flow is hard to make reliable and observable in a
2-day build; an explicit graph is inspectable and streamable node-by-node, which
is exactly what the progress UI needs. The SQLite checkpointer was low-effort
(LangGraph ships `SqliteSaver`) for a real recoverability story.

---

## Decision 3 — Async background execution + SSE for live progress

**What I did.** `POST /run` starts the graph in an asyncio background task and
returns `202` immediately. Each completed node is persisted to an `events` table
**and** published to an in-memory pub/sub that a `GET /stream` **SSE** endpoint
fans out to the browser. The stream replays persisted history before going live,
so opening it at any time shows the full picture.

**Alternatives considered.**
- *Synchronous request* that blocks until the report is done.
- *Client polling* an events endpoint on a timer.
- *WebSockets* for bidirectional streaming.
- *A real task queue* (Celery/RQ + Redis).

**Tradeoffs & why.** A synchronous run would hang the request for the full
workflow duration and give the user a spinner with no insight — the opposite of
the "display progress" requirement. Polling works (and I kept the `/events`
endpoint as a fallback) but wastes requests and lags real time. WebSockets are
overkill since progress is one-directional. A task queue is the *correct*
production answer for durability and horizontal scale, but it's heavy
infrastructure for a single-node take-home; I documented it as the next step in
`architecture.md` and `product-improvements.md` instead. The
persist-then-publish pattern means the durable audit trail and the live feed
come from the same source of truth, and a late-joining client never misses
events.

---

## Bonus — What I'd improve with two more weeks

1. **Grounded citations + per-claim confidence** — attach each report claim to a
   verified source snippet and add a verification node (the #1 trust gap).
2. **Durable, scalable execution** — move runs onto a task queue with a Redis
   pub/sub for SSE fan-out, and use the existing LangGraph checkpointer to resume
   interrupted runs after a restart.
3. **Auth + multi-tenancy** — users, per-tenant data isolation, and API
   cost/rate quotas, so it's safe to expose beyond a demo.
4. **Objective-adaptive planning + streaming report generation** — branch the
   research strategy on the objective and stream report tokens as they're
   written for a snappier feel.
5. **Observability & evaluation** — request tracing, per-node latency/cost
   metrics, and an offline eval harness that scores report quality against a
   rubric so changes to prompts/graph can be measured, not guessed.
