import { useEffect, useRef, useState } from "react";
import { api } from "../api";

const ICON = { completed: "✓", failed: "✕", running: "…" };

// Renders the workflow as a live timeline. Because the SSE endpoint replays
// persisted history before streaming live events, this shows the full picture
// whether the run is in-flight or finished — including retry loops (a node can
// legitimately appear more than once).
export default function WorkflowProgress({ sessionId, status, onComplete }) {
  const [steps, setSteps] = useState([]);
  const [connected, setConnected] = useState(false);
  const seenSeq = useRef(new Set());
  const esRef = useRef(null);

  useEffect(() => {
    setSteps([]);
    seenSeq.current = new Set();

    const es = new EventSource(api.streamUrl(sessionId));
    esRef.current = es;

    es.onopen = () => setConnected(true);
    es.onmessage = (msg) => {
      let data;
      try {
        data = JSON.parse(msg.data);
      } catch {
        return;
      }
      if (data.type === "event") {
        if (seenSeq.current.has(data.seq)) return;
        seenSeq.current.add(data.seq);
        setSteps((prev) => [...prev, data]);
      } else if (data.type === "done") {
        es.close();
        setConnected(false);
        onComplete?.(data.status);
      }
    };
    es.onerror = () => {
      // The stream closes itself after "done"; only surface unexpected drops.
      setConnected(false);
    };

    return () => es.close();
    // Reconnect when the session changes or a new run starts (status flips to running).
  }, [sessionId, status === "running"]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!steps.length && status === "created") {
    return (
      <p className="muted">Run the workflow to see live progress here.</p>
    );
  }

  return (
    <div className="progress">
      {status === "running" && (
        <div className="progress-live">
          <span className="spinner" /> Workflow running
          {connected ? " (live)" : ""}…
        </div>
      )}
      <ol className="timeline">
        {steps.map((s) => (
          <li key={s.seq} className={`timeline-item ti-${s.status}`}>
            <span className="ti-icon">{ICON[s.status] || "•"}</span>
            <div className="ti-body">
              <div className="ti-label">
                {s.label}
                <span className="ti-node">{s.node}</span>
              </div>
              <StepDetail payload={s.payload} />
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function StepDetail({ payload }) {
  if (!payload) return null;
  return (
    <div className="ti-detail">
      {payload.plan && (
        <ul className="ti-list">
          {payload.plan.map((p, i) => (
            <li key={i}>{p}</li>
          ))}
        </ul>
      )}
      {payload.findings_count != null && (
        <span className="ti-chip">
          {payload.findings_count} findings · {payload.sources_count} sources
        </span>
      )}
      {payload.quality_score != null && (
        <span className="ti-chip">
          quality {Number(payload.quality_score).toFixed(2)} ·{" "}
          {payload.quality_passed ? "passed" : "needs work"}
        </span>
      )}
      {payload.errors?.length > 0 && (
        <div className="alert alert-warn">{payload.errors.join("; ")}</div>
      )}
    </div>
  );
}
