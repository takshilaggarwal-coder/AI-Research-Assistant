# Architecture

## 1. How the layers connect

```
                     HTTP (JSON)          in-process call
  ┌────────────┐   POST /sessions      ┌──────────────────┐   stream_run()   ┌────────────────────┐
  │            │ ────────────────────▶ │                  │ ───────────────▶ │  LangGraph engine  │
  │  React SPA │   POST /run           │  FastAPI (ASGI)  │                  │                    │
  │  (Vite)    │ ────────────────────▶ │                  │   node updates   │  planner           │
  │            │                       │  routers/        │ ◀─────────────── │  research          │
  │            │   GET /stream (SSE)   │  services/       │                  │  analysis          │
  │            │ ◀──────event stream── │  runner (async)  │                  │  quality_check ⟲   │
  │            │                       │                  │                  │  refine            │
  │            │   POST /chat          │                  │                  │  report            │
  └────────────┘ ────────────────────▶ └────────┬─────────┘                  └─────────┬──────────┘
                                                 │ read/write                          │ checkpoint
                                                 ▼                                     ▼
                                      ┌───────────────────────┐          ┌──────────────────────────┐
                                      │ SQLite: copilot.db     │          │ SQLite: checkpoints.db   │
                                      │ sessions/events/msgs   │          │ LangGraph state per run  │
                                      └───────────────────────┘          └──────────────────────────┘

                        LLM + Search are pluggable providers behind interfaces:
                        Anthropic ─┐                         Tavily ─┐
                        Stub ──────┴─▶ llm.get_llm()         DuckDuckGo ─┴─▶ search()
                                                             Stub ─┘
```

## 2. One paragraph per layer

**Frontend — React + Vite.** A single-page app with client-side routing. I chose
React because the assignment requires it and its component model maps cleanly to
the four screens (create, history, detail, chat). Vite gives instant dev startup
and a built-in `/api` proxy so development needs no CORS configuration. Live
workflow progress uses the browser-native `EventSource` (SSE) API — no websocket
server or polling library required. State is kept deliberately local to
components; the app is small enough that a global store (Redux/Zustand) would be
overhead, not leverage.

**Backend — Python + FastAPI.** FastAPI was chosen for first-class async support
(needed to run the workflow in the background while streaming progress),
automatic request/response validation via Pydantic, and free OpenAPI docs. The
backend is layered: thin **routers** handle HTTP, a **service layer** holds all
business logic (LLM, search, persistence, the run orchestrator), and nothing but
`store.py` touches SQL. This keeps each piece independently testable and makes
the storage engine swappable.

**AI workflow — LangGraph.** The core requirement. A `StateGraph` threads one
typed `ResearchState` object through six nodes. LangGraph (over a hand-rolled
loop or a linear chain) gives me three things I'd otherwise have to build:
declarative **conditional edges**, streamable intermediate state after every
node, and a pluggable **checkpointer** for recoverability. The `.stream()` API
is what powers the live progress feed.

**Storage — SQLite.** Two SQLite databases: one for application data (sessions,
the append-only workflow event log, chat messages) and one used by LangGraph's
`SqliteSaver` checkpointer. SQLite needs zero setup, is durable across restarts,
and is more than enough for this workload. WAL mode plus a short-lived
connection per operation gives safe concurrent access across FastAPI's
threadpool. The repository pattern (`services/store.py`) means moving to Postgres
later is a one-file change.

## 3. Data flow: user input → final report

1. **Create.** The React form POSTs `{company_name, website, objective}` to
   `/api/sessions`. A row is inserted with status `created`; the id is returned.
2. **Run.** The detail page POSTs `/api/sessions/{id}/run`. The `RunManager`
   marks the session `running` and launches the workflow as a background
   asyncio task (the HTTP call returns `202` immediately).
3. **Execute.** The run driver calls `workflow.stream_run(state, thread_id=id)`.
   LangGraph executes nodes in order:
   - **planner** turns the objective into a plan + search queries;
   - **research** runs each query through the search provider, collecting
     findings and de-duplicated sources;
   - **analysis** synthesizes findings into a structured analysis;
   - **quality_check** scores the analysis. A **conditional edge** routes to
     `refine → research` (a retry loop) if the score is below threshold and
     retries remain, otherwise to `report`;
   - **report** composes the final briefing with all required sections.
4. **Stream.** After each node, the driver persists an event row and publishes it
   to any SSE subscribers. The browser's `EventSource` renders the progress
   timeline in real time. LangGraph checkpoints state after each node.
5. **Finish.** On completion the final report is written to the session row and
   status flips to `completed`; a `done` event closes the stream.
6. **Chat.** Follow-up questions POST to `/api/sessions/{id}/chat`. The handler
   loads the stored report, builds a grounded prompt (report + recent history),
   and returns the model's answer, persisting both turns.

## 4. Notable tradeoffs and constraints

- **Offline-first provider abstraction.** The biggest design decision was making
  the LLM and search layers degrade to a deterministic stub instead of hard-
  failing without keys. The tradeoff: stub output is placeholder text, not real
  research. I accepted that because a reviewer being able to run the *entire*
  product in one command is worth more than requiring paid keys to see anything
  at all. The stub is explicitly labelled so it can never be mistaken for real
  findings.
- **Background task + SSE vs. a job queue.** For a single-process app, running
  the graph in an asyncio background task with an in-memory pub/sub for SSE is
  simple and correct. It does **not** survive a process restart mid-run and
  won't scale horizontally (see `product-improvements.md`). A real deployment
  would move to Celery/RQ or a durable queue and a shared broker (Redis) for
  fan-out. The LangGraph checkpointer already lays the groundwork for resuming
  interrupted runs.
- **SSE over WebSockets.** Progress is one-directional (server → client), so SSE
  is the simpler fit — it's just an HTTP response, works through the Vite proxy,
  and reconnects natively. The cost is no client→server channel on that
  connection, which we don't need.
- **SQLite over Postgres.** Zero-setup and durable, at the cost of write
  concurrency and no network access. Fine for a single-node demo; the repository
  boundary keeps the upgrade path short.
- **Two SQLite files.** App data and LangGraph checkpoints are kept separate so
  the checkpointer's schema (owned by LangGraph) never collides with ours.
