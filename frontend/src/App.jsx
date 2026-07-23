import { useCallback, useEffect, useState } from "react";
import { Routes, Route, Link, useNavigate } from "react-router-dom";
import { api } from "./api";
import SessionForm from "./components/SessionForm.jsx";
import SessionList from "./components/SessionList.jsx";
import SessionDetail from "./components/SessionDetail.jsx";

export default function App() {
  const [sessions, setSessions] = useState([]);
  const [health, setHealth] = useState(null);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const navigate = useNavigate();

  const refreshSessions = useCallback(async () => {
    try {
      const data = await api.listSessions();
      setSessions(data);
    } catch (e) {
      console.error("Failed to load sessions", e);
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  useEffect(() => {
    refreshSessions();
    api.health().then(setHealth).catch(() => setHealth(null));
  }, [refreshSessions]);

  const handleCreated = async (session) => {
    await refreshSessions();
    navigate(`/sessions/${session.id}`);
  };

  const handleDeleted = async (id) => {
    await api.deleteSession(id);
    await refreshSessions();
    navigate("/");
  };

  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark">/zylabs</span>
          <span className="brand-title">AI Research Copilot</span>
        </Link>
        {health && (
          <div className="modes" title="Active providers">
            <span className={`pill pill-${health.llm_mode}`}>LLM: {health.llm_mode}</span>
            <span className={`pill pill-${health.search_mode}`}>
              Search: {health.search_mode}
            </span>
          </div>
        )}
      </header>

      <div className="layout">
        <aside className="sidebar">
          <Link to="/" className="btn btn-primary btn-block">
            + New research
          </Link>
          <SessionList
            sessions={sessions}
            loading={loadingSessions}
            onDelete={handleDeleted}
          />
        </aside>

        <main className="content">
          <Routes>
            <Route path="/" element={<SessionForm onCreated={handleCreated} />} />
            <Route
              path="/sessions/:id"
              element={
                <SessionDetail
                  onSessionChanged={refreshSessions}
                  onDelete={handleDeleted}
                />
              }
            />
          </Routes>
        </main>
      </div>
    </div>
  );
}
