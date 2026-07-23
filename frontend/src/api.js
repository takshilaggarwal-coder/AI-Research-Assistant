// Thin API client. All calls go through one place so error handling and the
// base URL are consistent. In dev, Vite proxies /api to the FastAPI backend.

const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  health: () => request("/health"),

  createSession: (payload) =>
    request("/sessions", { method: "POST", body: JSON.stringify(payload) }),
  listSessions: () => request("/sessions"),
  getSession: (id) => request(`/sessions/${id}`),
  deleteSession: (id) => request(`/sessions/${id}`, { method: "DELETE" }),

  runWorkflow: (id) => request(`/sessions/${id}/run`, { method: "POST" }),
  getEvents: (id) => request(`/sessions/${id}/events`),

  getMessages: (id) => request(`/sessions/${id}/messages`),
  sendChat: (id, message) =>
    request(`/sessions/${id}/chat`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),

  // Returns an EventSource for the live progress stream.
  streamUrl: (id) => `${BASE}/sessions/${id}/stream`,
};
