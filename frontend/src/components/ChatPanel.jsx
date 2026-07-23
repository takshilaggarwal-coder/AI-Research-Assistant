import { useEffect, useRef, useState } from "react";
import { api } from "../api";

// Follow-up chat grounded in the finished report. Disabled until the workflow
// has completed, since answers are derived from the report context.
export default function ChatPanel({ sessionId, enabled }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    if (!enabled) return;
    api.getMessages(sessionId).then(setMessages).catch(() => {});
  }, [sessionId, enabled]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  const send = async (e) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;
    setError(null);
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setSending(true);
    try {
      const res = await api.sendChat(sessionId, text);
      setMessages((m) => [...m, { role: "assistant", content: res.reply }]);
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  };

  if (!enabled) {
    return (
      <p className="muted">
        Chat becomes available once the research report is ready.
      </p>
    );
  }

  return (
    <div className="chat">
      <div className="chat-messages">
        {messages.length === 0 && (
          <p className="muted">
            Ask a follow-up, e.g. “What's the best opening line for outreach?”
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`bubble bubble-${m.role}`}>
            {m.content}
          </div>
        ))}
        {sending && <div className="bubble bubble-assistant typing">…</div>}
        <div ref={bottomRef} />
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <form className="chat-input" onSubmit={send}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about this company…"
          disabled={sending}
        />
        <button className="btn btn-primary" disabled={sending || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
