import React from "react";
import { useEffect, useRef, useState } from "react";
import { AssistantMessage } from "./openui.jsx";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const EXAMPLES = [
  "Plan a 5-day holiday to Switzerland from Delhi with 1.5 lakh budget",
  "Weekend trip to Goa from Bangalore with 15k budget for 2 friends",
  "What are the Schengen visa requirements for Indians?",
  "Spiritual trip to Vaishno Devi with family for 3 days",
];

function createSessionId() {
  return `session_${crypto.randomUUID()}`;
}

function initialSessionId() {
  const stored = sessionStorage.getItem("travel-session-id");
  if (stored) return stored;
  const created = createSessionId();
  sessionStorage.setItem("travel-session-id", created);
  return created;
}

function loadMessages(sessionId) {
  try {
    const stored = sessionStorage.getItem(`travel-messages-${sessionId}`);
    const messages = stored ? JSON.parse(stored) : [];
    return Array.isArray(messages) ? messages : [];
  } catch (error) {
    console.warn("Could not restore the chat transcript from this browser session.", error);
    return [];
  }
}

function eventFromFrame(frame, onToken) {
  const data = frame
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trim())
    .join("\n");
  if (!data) return;

  const eventName =
    frame.match(/^event:\s*(.+)$/m)?.[1]?.trim() ?? "message";
  const payload = JSON.parse(data);
  if (eventName === "token") onToken(payload.text ?? "");
  if (eventName === "error") throw new Error(payload.message ?? "Request failed.");
}

function Message({ message, isStreaming }) {
  const isUser = message.role === "user";
  return (
    <article className={`message-row ${isUser ? "message-row-user" : ""}`}>
      {!isUser && <div className="assistant-avatar">✦</div>}
      <div className={`message-content ${isUser ? "user-bubble" : "assistant-content"}`}>
        {isUser ? (
          <p>{message.content}</p>
        ) : message.content ? (
          <AssistantMessage content={message.content} isStreaming={isStreaming} />
        ) : (
          <div className="thinking"><span /><span /><span /> Planning your answer</div>
        )}
      </div>
      {isUser && <div className="user-avatar">Y</div>}
    </article>
  );
}

export default function App() {
  const [sessionId, setSessionId] = useState(initialSessionId);
  const [messages, setMessages] = useState(() => loadMessages(sessionId));
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [error, setError] = useState("");
  const abortRef = useRef(null);
  const transcriptRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    transcriptRef.current?.scrollTo({
      top: transcriptRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  useEffect(() => {
    sessionStorage.setItem(`travel-messages-${sessionId}`, JSON.stringify(messages));
  }, [messages, sessionId]);

  useEffect(() => () => abortRef.current?.abort(), []);

  async function sendMessage(value = draft) {
    const text = value.trim();
    if (!text || isSending) return;

    const assistantId = crypto.randomUUID();
    setError("");
    setDraft("");
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", content: text },
      { id: assistantId, role: "assistant", content: "" },
    ]);
    setIsSending(true);

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const response = await fetch(`${API_BASE}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: text }),
        signal: controller.signal,
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || `Request failed (${response.status}).`);
      }
      if (!response.body) throw new Error("The server did not start a response stream.");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      const appendToken = (token) => {
        if (!token) return;
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantId
              ? { ...message, content: message.content + token }
              : message,
          ),
        );
      };

      while (true) {
        const { value: bytes, done } = await reader.read();
        buffer += decoder.decode(bytes ?? new Uint8Array(), { stream: !done });
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";
        for (const frame of frames) eventFromFrame(frame, appendToken);
        if (done) break;
      }
      if (buffer.trim()) eventFromFrame(buffer, appendToken);
    } catch (requestError) {
      if (requestError.name !== "AbortError") {
        setError(requestError.message || "Unable to reach the travel assistant.");
        setMessages((current) =>
          current.filter((message) => message.id !== assistantId || message.content),
        );
      }
    } finally {
      setIsSending(false);
      abortRef.current = null;
      inputRef.current?.focus();
    }
  }

  function startNewTrip() {
    abortRef.current?.abort();
    const nextSession = createSessionId();
    sessionStorage.setItem("travel-session-id", nextSession);
    setSessionId(nextSession);
    setMessages([]);
    setDraft("");
    setError("");
    setIsSending(false);
    inputRef.current?.focus();
  }

  function downloadTranscript() {
    const transcript = messages
      .map((message) => {
        const role = message.role === "user" ? "You" : "Wayfarer";
        return `## ${role}\n\n${message.content}`;
      })
      .join("\n\n---\n\n");
    const blob = new Blob([transcript], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `travel-plan-${sessionId}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar${isSidebarCollapsed ? " sidebar-collapsed" : ""}`}>
        <div className="sidebar-brand-row">
          <a className="brand" href="#" aria-label="Wayfarer home">
            <span className="brand-mark">W</span>
            <span className="brand-name">wayfarer<span className="brand-period">.</span></span>
          </a>
          <button
            className="sidebar-toggle"
            type="button"
            onClick={() => setIsSidebarCollapsed((collapsed) => !collapsed)}
            aria-label={isSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!isSidebarCollapsed}
            title={isSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {isSidebarCollapsed ? "»" : "«"}
          </button>
        </div>

        <button className="new-trip-button" onClick={startNewTrip}>
          <span>＋</span> Start a new trip
        </button>

        <section className="sidebar-section session-section">
          <div className="section-label">YOUR SESSION</div>
          <div className="session-card">
            <span className="session-status" />
            <div className="session-details">
              <span>Active conversation</span>
              <code>{sessionId.slice(0, 18)}…</code>
            </div>
            <span className="session-lock" title="Private to this session">⌑</span>
          </div>
          <p className="sidebar-note">Your conversation stays in memory while this server is running.</p>
        </section>

        <section className="sidebar-section examples-section">
          <div className="section-heading">
            <span className="section-label">EXAMPLE QUERIES</span>
            <span className="sparkle">✳</span>
          </div>
          <div className="example-list">
            {EXAMPLES.map((example, index) => (
              <button
                className="example-button"
                key={example}
                onClick={() => sendMessage(example)}
                disabled={isSending}
              >
                <span className={`example-icon example-icon-${index}`}>
                  {["◒", "⌁", "◇", "✧"][index]}
                </span>
                <span>{example}</span>
                <span className="example-arrow">↗</span>
              </button>
            ))}
          </div>
        </section>

        <div className="sidebar-footer">
          {messages.length > 0 && (
            <button className="download-button" onClick={downloadTranscript}>
              <span>↓</span> Download chat transcript
            </button>
          )}
          <div className="footer-profile">
            <div className="profile-avatar">✦</div>
            <div><strong>Travel planner</strong><span>Ready for your next journey</span></div>
            <span className="profile-menu">···</span>
          </div>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div className="topbar-title">
            <span className="mobile-brand-mark">W</span>
            <span>Travel assistant</span>
            <span className="topbar-divider">/</span>
            <span className="topbar-subtitle">Plan with confidence</span>
          </div>
          <div className="topbar-right">
            <span className="live-indicator"><i /> Live research</span>
            <button className="topbar-reset" onClick={startNewTrip}>New trip <span>↗</span></button>
          </div>
        </header>

        <div className="conversation" ref={transcriptRef}>
          {messages.length === 0 ? (
            <section className="welcome">
              <div className="welcome-eyebrow"><span>✦</span> A BETTER WAY TO GET THERE</div>
              <h1>Where will your<br /><em>curiosity</em> take you?</h1>
              <p className="welcome-copy">
                Thoughtful itineraries, real-world details, and a little inspiration
                for wherever you’re headed next.
              </p>
              <div className="suggestion-heading">A few places to begin</div>
              <div className="suggestion-grid">
                {EXAMPLES.map((example, index) => (
                  <button
                    className="suggestion-card"
                    key={example}
                    onClick={() => sendMessage(example)}
                    disabled={isSending}
                  >
                    <span className={`suggestion-symbol suggestion-symbol-${index}`}>
                      {["↗", "⌁", "◇", "✧"][index]}
                    </span>
                    <span>{example}</span>
                    <span className="suggestion-arrow">↗</span>
                  </button>
                ))}
              </div>
              <div className="welcome-footnote"><span>✳</span> Verified travel insights, tailored to you</div>
            </section>
          ) : (
            <div className="message-list">
              <div className="conversation-date"><span /> YOUR TRAVEL CONVERSATION <span /></div>
              {messages.map((message) => (
                <Message
                  key={message.id}
                  message={message}
                  isStreaming={isSending && message.role === "assistant" && message.id === messages.at(-1)?.id}
                />
              ))}
              {error && <div className="error-banner" role="alert">{error}</div>}
            </div>
          )}
        </div>

        <footer className="composer-wrap">
          {error && messages.length === 0 && <div className="error-banner composer-error" role="alert">{error}</div>}
          <form
            className="composer"
            onSubmit={(event) => {
              event.preventDefault();
              sendMessage();
            }}
          >
            <textarea
              ref={inputRef}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Ask about a destination, route, visa, or anything travel…"
              rows={1}
              disabled={isSending}
              aria-label="Message the travel assistant"
            />
            <div className="composer-bottom">
              <span className="composer-hint"><kbd>↵</kbd> to send <span>·</span> <kbd>⇧ ↵</kbd> for a new line</span>
              <button className="send-button" type="submit" disabled={!draft.trim() || isSending} aria-label="Send message">
                {isSending ? <span className="send-spinner" /> : <span>↑</span>}
              </button>
            </div>
          </form>
          <p className="disclaimer">Travel details are researched live. Please verify time-sensitive bookings with providers.</p>
        </footer>
      </main>
    </div>
  );
}
