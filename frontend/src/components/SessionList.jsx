import { NavLink } from "react-router-dom";

const STATUS_LABEL = {
  created: "Draft",
  running: "Running",
  completed: "Done",
  failed: "Failed",
};

export default function SessionList({ sessions, loading, onDelete }) {
  if (loading) {
    return <div className="session-list muted">Loading sessions…</div>;
  }
  if (!sessions.length) {
    return <div className="session-list muted">No sessions yet.</div>;
  }

  return (
    <nav className="session-list">
      <div className="session-list-title">History</div>
      {sessions.map((s) => (
        <NavLink
          key={s.id}
          to={`/sessions/${s.id}`}
          className={({ isActive }) =>
            `session-item ${isActive ? "active" : ""}`
          }
        >
          <div className="session-item-main">
            <div className="session-item-name">{s.company_name}</div>
            <div className="session-item-objective">{s.objective}</div>
          </div>
          <div className="session-item-meta">
            <span className={`status status-${s.status}`}>
              {STATUS_LABEL[s.status] || s.status}
            </span>
            <button
              className="icon-btn"
              title="Delete session"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                if (confirm(`Delete research for ${s.company_name}?`)) onDelete(s.id);
              }}
            >
              ×
            </button>
          </div>
        </NavLink>
      ))}
    </nav>
  );
}
