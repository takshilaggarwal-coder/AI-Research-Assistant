import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import WorkflowProgress from "./WorkflowProgress.jsx";
import ReportView from "./ReportView.jsx";
import ChatPanel from "./ChatPanel.jsx";

export default function SessionDetail({ onSessionChanged, onDelete }) {
  const { id } = useParams();
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [starting, setStarting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setSession(await api.getSession(id));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const runWorkflow = async () => {
    setStarting(true);
    setError(null);
    try {
      await api.runWorkflow(id);
      setSession((s) => ({ ...s, status: "running" }));
    } catch (e) {
      setError(e.message);
    } finally {
      setStarting(false);
    }
  };

  // Called by WorkflowProgress when the SSE stream reports completion.
  const handleComplete = useCallback(async () => {
    await load();
    onSessionChanged?.();
  }, [load, onSessionChanged]);

  if (loading) return <div className="panel">Loading session…</div>;
  if (error && !session)
    return <div className="panel alert alert-error">{error}</div>;
  if (!session) return null;

  const isDone = session.status === "completed";
  const canRun = session.status === "created" || session.status === "failed";

  return (
    <div className="detail">
      <div className="panel detail-header">
        <div>
          <h1>{session.company_name}</h1>
          {session.website && (
            <a href={session.website} target="_blank" rel="noreferrer" className="muted">
              {session.website}
            </a>
          )}
          <p className="objective">
            <strong>Objective:</strong> {session.objective}
          </p>
          <span className={`status status-${session.status}`}>{session.status}</span>
        </div>
        <div className="detail-actions">
          {canRun && (
            <button className="btn btn-primary" onClick={runWorkflow} disabled={starting}>
              {starting
                ? "Starting…"
                : session.status === "failed"
                ? "Retry workflow"
                : "Run workflow"}
            </button>
          )}
          <button className="btn btn-ghost" onClick={() => onDelete(id)}>
            Delete
          </button>
        </div>
      </div>

      {error && <div className="panel alert alert-error">{error}</div>}
      {session.error && (
        <div className="panel alert alert-error">Workflow error: {session.error}</div>
      )}

      <div className="detail-grid">
        <section className="panel">
          <h2>Workflow progress</h2>
          <WorkflowProgress
            sessionId={id}
            status={session.status}
            onComplete={handleComplete}
          />
        </section>

        <section className="panel">
          <h2>Research briefing</h2>
          {isDone ? (
            <ReportView report={session.report} />
          ) : (
            <p className="muted">
              The structured briefing appears here once the workflow completes.
            </p>
          )}
        </section>
      </div>

      <section className="panel">
        <h2>Follow-up chat</h2>
        <ChatPanel sessionId={id} enabled={isDone} />
      </section>
    </div>
  );
}
