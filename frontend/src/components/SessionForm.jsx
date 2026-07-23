import { useState } from "react";
import { api } from "../api";

const EXAMPLES = [
  {
    company_name: "Notion",
    website: "https://notion.so",
    objective: "Pitch our enterprise onboarding automation platform",
  },
  {
    company_name: "Databricks",
    website: "https://databricks.com",
    objective: "Explore a partnership for data-governance tooling",
  },
];

export default function SessionForm({ onCreated }) {
  const [form, setForm] = useState({ company_name: "", website: "", objective: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const update = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    if (!form.company_name.trim() || !form.objective.trim()) {
      setError("Company name and research objective are required.");
      return;
    }
    setSubmitting(true);
    try {
      const session = await api.createSession(form);
      onCreated(session);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="panel form-panel">
      <h1>Start a research session</h1>
      <p className="muted">
        Give the copilot a company and what you want to achieve. It runs a
        multi-step LangGraph workflow and produces a structured meeting briefing.
      </p>

      <form onSubmit={submit} className="form">
        <label>
          Company name <span className="req">*</span>
          <input
            value={form.company_name}
            onChange={update("company_name")}
            placeholder="e.g. Stripe"
            autoFocus
          />
        </label>

        <label>
          Website
          <input
            value={form.website}
            onChange={update("website")}
            placeholder="https://stripe.com"
          />
        </label>

        <label>
          Research objective <span className="req">*</span>
          <textarea
            value={form.objective}
            onChange={update("objective")}
            rows={3}
            placeholder="e.g. Sell them a fraud-detection add-on and identify the right champion"
          />
        </label>

        {error && <div className="alert alert-error">{error}</div>}

        <button className="btn btn-primary" disabled={submitting}>
          {submitting ? "Creating…" : "Create session"}
        </button>
      </form>

      <div className="examples">
        <span className="muted">Or try an example:</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex.company_name}
            className="chip"
            onClick={() => setForm(ex)}
            type="button"
          >
            {ex.company_name}
          </button>
        ))}
      </div>
    </div>
  );
}
