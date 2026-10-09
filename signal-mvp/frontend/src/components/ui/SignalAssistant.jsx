import { useEffect, useRef, useState } from "react";
import { Bot, ChevronDown, ArrowUp, X } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { answerWithSignalData } from "../../api/assistant.js";
import "../../styles/signal-assistant.css";

const STARTER_QUESTIONS = [
  "How many patients and cases are in SIGNAL?",
  "Show cases needing review",
  "Which deadlines are coming up?",
  "Find a patient or case by name or ID",
];

export function SignalAssistant() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState([]);
  const [suggestions, setSuggestions] = useState(STARTER_QUESTIONS);
  const [previousTerm, setPreviousTerm] = useState("");
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy, open]);

  if (pathname === "/login") return null;

  async function ask(value) {
    const text = value.trim();
    if (!text || busy) return;
    setQuestion("");
    setBusy(true);
    setMessages((current) => [...current, { role: "user", text }]);
    try {
      const response = await answerWithSignalData(text, previousTerm);
      if (response.searchTerm) setPreviousTerm(response.searchTerm);
      setSuggestions(response.suggestions);
      setMessages((current) => [...current, {
        role: "assistant",
        text: response.answer,
        results: response.results,
        sourceErrors: response.sourceErrors,
      }]);
    } catch (error) {
      setMessages((current) => [...current, {
        role: "assistant",
        text: `I couldn't retrieve SIGNAL data. ${error.message}`,
        sourceErrors: [],
      }]);
    } finally {
      setBusy(false);
    }
  }

  function submit(event) {
    event.preventDefault();
    void ask(question);
  }

  return (
    <div className="signal-assistant">
      {open && (
        <section className="signal-assistant-panel" aria-label="ASK SIGNAL">
          <header className="signal-assistant-header">
            <span className="signal-assistant-logo"><Bot size={20} aria-hidden="true" /></span>
            <span className="signal-assistant-heading">
              <strong>ASK SIGNAL</strong>
              <small><i aria-hidden="true" /> Live backend data · stays in SIGNAL</small>
            </span>
            <button
              className="signal-assistant-close"
              type="button"
              aria-label="Close ASK SIGNAL"
              onClick={() => setOpen(false)}
            >
              <X size={18} />
            </button>
          </header>

          <div className="signal-assistant-messages" aria-live="polite">
            {!messages.length && (
              <div className="signal-assistant-welcome">
                <span className="signal-assistant-welcome-icon"><Bot size={23} aria-hidden="true" /></span>
                <strong>Ask about live SIGNAL data</strong>
                <p>I look up live patient, case, candidate, submission, follow-up, deadline, and analytics data.</p>
                <p className="signal-assistant-private-note">Your question and records are handled by SIGNAL; no external AI provider is used.</p>
              </div>
            )}
            {messages.map((message, index) => (
              <article className={`signal-assistant-message ${message.role}`} key={`${message.role}-${index}`}>
                <p>{message.text}</p>
                {message.results?.length > 0 && (
                  <div className="signal-assistant-results">
                    {message.results.map((result, resultIndex) => (
                      <button
                        className="signal-assistant-result"
                        type="button"
                        key={`${result.id || result.title}-${resultIndex}`}
                        onClick={() => {
                          if (result.href) {
                            navigate(result.href);
                            setOpen(false);
                          }
                        }}
                        disabled={!result.href}
                      >
                        <strong>{result.title}</strong>
                        {result.detail && <span>{result.detail}</span>}
                        {result.id && <small>{result.id}</small>}
                      </button>
                    ))}
                  </div>
                )}
                {message.sourceErrors?.length > 0 && (
                  <div className="signal-assistant-source-errors" role="status">
                    Some data sources were unavailable: {message.sourceErrors.join("; ")}
                  </div>
                )}
              </article>
            ))}
            {busy && <div className="signal-assistant-typing" role="status"><span /><span /><span /> Checking live SIGNAL data…</div>}
            <div ref={messagesEndRef} />
          </div>

          <div className="signal-assistant-suggestions" aria-label="Suggested questions">
            {suggestions.map((suggestion) => (
              <button type="button" key={suggestion} disabled={busy} onClick={() => void ask(suggestion)}>
                {suggestion}
              </button>
            ))}
          </div>
          <form className="signal-assistant-form" onSubmit={submit}>
            <label className="signal-assistant-sr-only" htmlFor="signal-assistant-question">Ask about SIGNAL data</label>
            <input
              id="signal-assistant-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask about patients, cases, deadlines…"
              autoComplete="off"
              disabled={busy}
            />
            <button type="submit" aria-label="Send question" disabled={busy || !question.trim()}>
              <ArrowUp size={17} aria-hidden="true" />
            </button>
          </form>
        </section>
      )}
      <button
        type="button"
        className={`signal-assistant-launcher${open ? " is-open" : ""}`}
        aria-expanded={open}
        aria-label={open ? "Close ASK SIGNAL" : "Open ASK SIGNAL"}
        onClick={() => setOpen((value) => !value)}
      >
        {open ? <ChevronDown size={19} aria-hidden="true" /> : <Bot size={20} aria-hidden="true" />}
        <span>{open ? "Close ASK SIGNAL" : "ASK SIGNAL"}</span>
      </button>
    </div>
  );
}
