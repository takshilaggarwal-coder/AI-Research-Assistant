# ZyLabs AI Research Copilot

> *"Your sellers run the conversation. We do everything else."*

A production-minded **AI Research Copilot** that helps someone prepare for a
sales or business meeting. You give it a company + a research objective; it runs
a multi-step **LangGraph** workflow (plan → research → analyze → quality-gate →
report), streams progress live, produces a structured briefing, and lets you ask
follow-up questions grounded in that briefing.

Built for the ZyLabs Intern AI Engineer assignment.

---

## ✨ Highlights

- **Real LangGraph workflow** — 6 nodes, shared typed state, **conditional
  routing** with a quality-gated retry loop, per-node failure handling, and
  **recoverability** via a SQLite checkpointer.
- **Live progress** — the workflow streams node-by-node updates to the UI over
  **Server-Sent Events** (with a polling fallback endpoint).
- **Runs with zero setup** — no API keys and no internet required. The LLM and
  web-search layers are abstracted behind provider interfaces that **gracefully
  fall back to a deterministic offline stub**, so a reviewer can run the entire
  product immediately. Add `ANTHROPIC_API_KEY` / `TAVILY_API_KEY` to upgrade to
  real model output and live web search — no code changes.
- **Persistence** — sessions, workflow event logs, and chat history in SQLite.
- **Production touches** — centralized config, structured logging, global error
  handling, CORS, health endpoint, and a smoke test for the graph.

---

## 🏗️ Architecture at a glance

```
┌──────────────┐     REST + SSE      ┌───────────────────┐
│  React (Vite)│ ──────────────────▶ │  FastAPI backend  │
│  - create    │ ◀────────────────── │  - session APIs   │
│  - history   │   JSON / event      │  - workflow APIs  │
│  - progress  │   stream            │  - chat APIs      │
│  - report    │                     └─────────┬─────────┘
│  - chat      │                               │ invokes
└──────────────┘                               ▼
                                    ┌───────────────────────┐
                                    │  LangGraph workflow    │
                                    │  planner→research→     │
                                    │  analysis→quality⟲     │
                                    │  →report               │
                                    └─────────┬──────────────┘
                                              │ persist
                                              ▼
                              ┌───────────────────────────────┐
                              │ SQLite: app data + checkpoints │
                              └───────────────────────────────┘
```

Full details in [`architecture.md`](architecture.md).

---

## 🚀 Quick start

You need **Python 3.9+** and **Node 18+**. Two terminals.

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# optional — copy and add keys to go from offline-stub to real model + search
cp .env.example .env

uvicorn app.main:app --reload --port 8000
```

Backend is now at `http://localhost:8000` (docs at `/docs`, health at
`/api/health`).

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **`http://localhost:5173`**. The Vite dev server proxies `/api` to the
backend, so no CORS setup is needed in development.

### 3. Try it

1. Enter a company (e.g. *Stripe*), an optional website, and an objective.
2. Click **Run workflow** and watch the live progress timeline.
3. Read the structured briefing.
4. Ask a follow-up question in the chat panel.

> **Offline note:** with no keys set, the header shows `LLM: stub`. The workflow,
> streaming, report, persistence, and chat all still work end-to-end — the text
> is deterministic placeholder content, clearly labelled as such. `ddgs` may
> still return **real** web sources when a network is available.

---

## 🧪 Tests

```bash
cd backend
source .venv/bin/activate
python tests/test_graph.py          # or: python -m pytest -q
```

Verifies the graph runs every node in order and produces a report containing all
nine required sections — entirely offline.

---

## 📚 API reference (summary)

| Method | Path                              | Purpose                                   |
|--------|-----------------------------------|-------------------------------------------|
| POST   | `/api/sessions`                   | Create a research session                 |
| GET    | `/api/sessions`                   | List sessions (history)                   |
| GET    | `/api/sessions/{id}`              | Session detail incl. report               |
| DELETE | `/api/sessions/{id}`              | Delete a session                          |
| POST   | `/api/sessions/{id}/run`          | Start the LangGraph workflow (async)      |
| GET    | `/api/sessions/{id}/stream`       | **SSE** live workflow progress            |
| GET    | `/api/sessions/{id}/events`       | Persisted progress events (poll fallback) |
| POST   | `/api/sessions/{id}/chat`         | Ask a follow-up grounded in the report    |
| GET    | `/api/sessions/{id}/messages`     | Chat history                              |
| GET    | `/api/health`                     | Health + active provider modes            |

---

## 🗂️ Project layout

```
backend/
  app/
    graph/        state.py · nodes.py · workflow.py   (the LangGraph workflow)
    services/     llm.py · search.py · store.py · runner.py
    routers/      sessions.py · workflow.py · chat.py
    config.py · database.py · logging_config.py · schemas.py · main.py
  tests/          test_graph.py
frontend/
  src/
    components/   SessionForm · SessionList · SessionDetail
                  WorkflowProgress · ReportView · ChatPanel
    api.js · App.jsx · main.jsx · styles.css
docs/             screenshots / demo notes
architecture.md · product-improvements.md · engineering-decisions.md
```

---

## 📄 Documents

- [`architecture.md`](architecture.md) — how the layers connect, per-layer
  rationale, data flow, and tradeoffs.
- [`product-improvements.md`](product-improvements.md) — product weaknesses,
  prioritized roadmap, and business thinking.
- [`engineering-decisions.md`](engineering-decisions.md) — key decisions,
  alternatives considered, and tradeoffs.
