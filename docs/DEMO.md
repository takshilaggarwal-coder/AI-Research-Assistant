# Demo notes

## Running the product for a demo / recording

1. **Start the backend** (offline stub mode needs no keys):
   ```bash
   cd backend && python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```
2. **Start the frontend:**
   ```bash
   cd frontend && npm install && npm run dev
   ```
3. Open `http://localhost:5173`.

## Suggested 2-minute demo script

1. **Create a session** — company `Stripe`, objective
   *"Sell them a fraud-detection add-on."* Point out the header badges showing
   which LLM/search providers are active.
2. **Run the workflow** — narrate the live SSE progress timeline as each node
   completes: planning → gathering evidence (note the findings/sources count) →
   analysis → quality check (note the score) → briefing.
3. **Show the report** — walk through the nine sections; open a source link.
4. **Follow-up chat** — ask *"What's the strongest opening line for outreach?"*
   and show the grounded answer.
5. **History + persistence** — refresh the page; the session and report are still
   there. Open a second session to show the history sidebar.

## Showing the conditional retry loop (optional, impressive)

Set a strict quality threshold so the quality gate forces a retry:

```bash
QUALITY_THRESHOLD=0.99 MAX_RESEARCH_RETRIES=1 uvicorn app.main:app --port 8000
```

The progress timeline will show `quality_check → refine → research → analysis →
quality_check → report`, demonstrating the conditional edge and retry/refine
loop.

## Screenshots

Add screenshots or a screen recording here (e.g. `report.png`, `progress.png`)
before submitting, or link a hosted demo video.
